"""Ozon -> M.Video migration orchestration — v0.3 (OMNI + Excel-template).

v0.3 (2026-09-18) — MAJOR ARCHITECTURE SWITCH
=============================================
The traditional API (api.sellers.mvideo.ru) MaterialV2/PriceV2/StockV2 return
``400 API_KEY_INTERNAL_NOT_CONTAINS_KEY_TYPE`` for this seller account, so
auto-creating goods there is impossible. The SAME key authenticates against the
OMNI API (omni-net) for PRICE/STOCK writes. OMNI has NO product-create endpoint,
so goods are created by filling the M.Video Excel template and uploading it to
the web ЛК (``/mpa/products/import``); we then poll
``/v1/product/mapping/list`` to recover ``product_id`` from our ``offer_id``.

New pipeline (state machine on ``ItemStatus``):
  queued -> prepared (quality gate)
         -> images_processed (3:4 images mirrored to OSS, oss_images_json set)
         -> template_built    (build_template_rows produced the .xlsx payload)
         -> template_uploaded (mark_uploaded: external Excel upload done)
         -> mapping_pending   (polling /v1/product/mapping/list)
         -> product_matched   (offer_id -> product_id resolved)
         -> priced (OMNI price/update, RUB) -> stocked (OMNI stock/update)  SUCCESS
  any failure -> needs_review / waiting_quota / failed.

Every stage ends with reconcile_batch() so sum(item statuses) == total_count.

DEPRECATED (kept for old rows / reference, NOT used by the v0.3 pipeline):
  run_submit()    — old MaterialV2 create (traditional API, no permission)
  poll_moderation() — old taskStatus moderation poll (traditional API)
The traditional MaterialV2/PriceV2/StockV2 client (app.integrations.mvideo_client)
is retained; only ``check_connection`` is still useful (key connectivity probe).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.currency import build_price_item, build_stock_item
from app.models import (
    BatchStatus,
    ItemStatus,
    LegacyMaterialStatus,
    MigrationBatch,
    MigrationItem,
)
from app.pipeline.mapping import resolve_category
from app.pipeline.reconcile import reconcile_batch
from app.pipeline.template_builder import build_template_rows
from app.quality_gate import run_quality_gate

log = logging.getLogger("mvideo.pipeline")


# --------------------------------------------------------------------------- #
# Defensive Ozon response extractors (unchanged from v0.2)
# --------------------------------------------------------------------------- #
def _first_attr(attrs: list, *name_hints: str):
    for a in attrs or []:
        if not isinstance(a, dict):
            continue
        nm = str(a.get("name", "")).lower()
        if any(h in nm for h in name_hints):
            vals = a.get("values") or []
            if vals and isinstance(vals[0], dict):
                return str(vals[0].get("value", ""))
            if vals:
                return str(vals[0])
    return ""


def _attr_by_id(attrs: list, want_id: int) -> str:
    """v4 attributes use numeric ``id`` (no name) — look up by known id."""
    for a in attrs or []:
        if isinstance(a, dict) and int(a.get("id") or -1) == want_id:
            vals = a.get("values") or []
            if vals and isinstance(vals[0], dict):
                return str(vals[0].get("value", ""))
            if vals:
                return str(vals[0])
    return ""


def _extract_ozon(attr_body: dict, price_body: dict) -> dict:
    """Pull the fields we need out of the Ozon attribute + price responses.

    Real v4 shape (verified 2026-09-18): barcode/name/primary_image/
    description_category_id are TOP LEVEL; ``attributes[]`` entries carry a
    numeric ``id`` (brand=85), no human ``name``.
    """
    result = attr_body.get("result") or attr_body.get("items") or []
    prod = result[0] if isinstance(result, list) and result else {}
    if not isinstance(prod, dict):
        prod = {}

    attrs = prod.get("attributes") or []

    cat_id = int(prod.get("description_category_id") or prod.get("type_id") or 0)
    cat_name = str(prod.get("description_category_name", "") or "")

    images = list(prod.get("images") or [])
    if prod.get("primary_image"):
        images = [prod["primary_image"]] + images
    images = [u for u in images if isinstance(u, str) and u.startswith("http")]

    # Pack dimensions: Ozon v4 top-level width/height/depth(mm), weight(g).
    # M.Video wants cm / kg. length <- depth.
    def _mm_to_cm(v):
        try:
            return round(float(v) / 10.0, 2)
        except (TypeError, ValueError):
            return 0.0

    length_cm = _mm_to_cm(prod.get("depth"))
    width_cm = _mm_to_cm(prod.get("width"))
    height_cm = _mm_to_cm(prod.get("height"))
    try:
        weight_kg = round(float(prod.get("weight") or 0) / 1000.0, 3)
    except (TypeError, ValueError):
        weight_kg = 0.0
    dims = {
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
    }

    barcode = str(prod.get("barcode") or "")
    if not barcode:
        bc = prod.get("barcodes") or []
        if bc:
            barcode = str(bc[0])
    if not barcode:
        barcode = _first_attr(attrs, "баркод", "barcode", "штрихкод", "штрих-код")

    # brand: v4 attr id=85 is the brand; name-hint fallback for older shapes.
    brand = _attr_by_id(attrs, 85) or _first_attr(attrs, "бренд", "brand")

    price = Decimal("0")
    try:
        info_items = price_body.get("items") or price_body.get("result") or []
        if info_items:
            raw_price = info_items[0].get("price")
            if isinstance(raw_price, dict):
                raw_price = raw_price.get("price")
            price = Decimal(str(raw_price or "0"))
        if price == 0:
            pr_items = price_body.get("items") or []
            if pr_items:
                pr = pr_items[0].get("price", {}) or {}
                price = Decimal(str(pr.get("price") or "0"))
    except Exception:  # noqa: BLE001 - price is non-critical
        price = Decimal("0")

    # description: Ozon v4 attr id=4191 holds an HTML string. Strip tags in
    # the template builder; here we just carry the raw text through.
    desc_raw = _attr_by_id(attrs, 4191)

    name = str(prod.get("name", "") or "").strip()
    # M.Video product name cap ~249 chars (per template hint); truncate with ellipsis.
    if len(name) > 249:
        name = name[:246].rstrip() + "..."

    return {
        "name": name,
        "brand": brand,
        "description": desc_raw,
        "category_id": cat_id,
        "category_name": cat_name,
        "attributes": attrs,
        "images": images,
        "barcode": barcode,
        "price": price,
        "dims": dims,
    }


# --------------------------------------------------------------------------- #
# Stage 1: pull from Ozon
# --------------------------------------------------------------------------- #
def pull_ozon_products(
    session,
    ozon,
    *,
    limit: int | None = None,
    batch_ref: str | None = None,
    note: str = "",
) -> MigrationBatch:
    settings = get_settings()
    ref = batch_ref or f"ozon2mv-{datetime.utcnow():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    batch = MigrationBatch(
        batch_ref=ref,
        source="ozon",
        status=BatchStatus.RUNNING,
        note=note,
    )
    session.add(batch)
    session.flush()

    count = 0
    consecutive_fail = 0
    for raw in ozon.iter_products(limit=100):
        pid = int(raw.get("product_id") or raw.get("id") or 0)
        if not pid:
            continue
        try:
            attr_body = ozon.get_product_attributes([pid])
        except Exception as exc:  # noqa: BLE001 - skip one bad product
            consecutive_fail += 1
            log.warning("ozon attributes failed for product %s: %s", pid, exc)
            if consecutive_fail >= 10:
                log.error("10 consecutive attribute failures — aborting pull to avoid scanning whole catalog")
                break
            continue
        consecutive_fail = 0
        try:
            price_body = ozon.get_prices([pid])
        except Exception as exc:  # noqa: BLE001 - price is best-effort, never block pull
            log.warning("ozon prices failed for product %s (non-fatal): %s", pid, exc)
            price_body = {}

        data = _extract_ozon(attr_body, price_body)
        cat = resolve_category(session, data["category_id"], data["category_name"])
        item = MigrationItem(
            batch_id=batch.id,
            ozon_product_id=pid,
            offer_id=raw.get("offer_id", "") or "",
            name=data["name"] or raw.get("name", ""),
            brand=data["brand"],
            ozon_category_id=data["category_id"],
            ozon_category_name=data["category_name"],
            attributes_json=data["attributes"],
            images_json=data["images"],
            source_barcode=data["barcode"],
            mv_group_id=cat.mv_group_id if cat else "",
            mv_infomodel_id=cat.mv_infomodel_id if cat else "",
            # NOTE: holds the Ozon CNY source price; converted to RUB at apply time.
            price_rub=data["price"],
            mv_length_cm=data["dims"]["length_cm"],
            mv_width_cm=data["dims"]["width_cm"],
            mv_height_cm=data["dims"]["height_cm"],
            mv_weight_kg=data["dims"]["weight_kg"],
            mv_description=data.get("description", ""),
            status=ItemStatus.QUEUED,
        )
        session.add(item)
        count += 1
        if limit is not None and count >= limit:
            break

    batch.total_count = count
    session.commit()
    log.info("pulled %d products into batch %s", count, ref)
    return batch


# --------------------------------------------------------------------------- #
# Stage 2: quality gate
# --------------------------------------------------------------------------- #
def run_prepare(session, *, batch_id: int | None = None) -> dict:
    settings = get_settings()
    stmt = select(MigrationItem).where(MigrationItem.status == ItemStatus.QUEUED)
    if batch_id is not None:
        stmt = stmt.where(MigrationItem.batch_id == batch_id)

    prepared = errored = 0
    for item in session.execute(stmt).scalars().all():
        if not (item.mv_nds or "").strip():
            item.mv_nds = settings.mv_tax_system
        tn_present = bool((item.mv_tn_ved or "").strip())
        gate_item = {
            "source_barcode": item.source_barcode,
            "name": item.name,
            "brand": item.brand,
            "mv_group_id": item.mv_group_id,
            "mv_infomodel_id": item.mv_infomodel_id,
            "mv_nds": item.mv_nds,
            "images": item.images_json or [],
            "dimensions": {
                "length_cm": item.mv_length_cm or 0,
                "width_cm": item.mv_width_cm or 0,
                "height_cm": item.mv_height_cm or 0,
                "weight_kg": item.mv_weight_kg or 0,
            },
        }
        report = run_quality_gate(
            gate_item,
            vendor_id=settings.mvideo_vendor_id,
            tn_ved_present=tn_present,
        )
        item.quality_report = report.report
        if report.ok:
            item.mv_barcode = report.barcode13
            item.status = ItemStatus.PREPARED
            prepared += 1
        else:
            item.status = ItemStatus.NEEDS_REVIEW
            item.last_error = "; ".join(report.errors)
            item.quality_report = {**report.report, "errors": report.errors}
            errored += 1
    session.commit()
    return {"prepared": prepared, "errored": errored}


# --------------------------------------------------------------------------- #
# Stage 3: images_processed (3:4 + OSS mirror -> oss_images_json)
# --------------------------------------------------------------------------- #
def run_images(session, uploader=None, *, batch_id: int | None = None, work_root: str = "") -> dict:
    """Real image stage: download Ozon CDN images -> 3:4 white-pad -> OSS mirror.

    For every PREPARED row with ``images_json`` (Ozon CDN URLs), download them,
    normalise to 900x1200 (3:4), upload to OSS, and store the public URLs in
    ``item.oss_images_json``. Rows that already have an OSS manifest are skipped.
    ``uploader`` defaults to OssUploader.from_settings() (credential-file aware).
    """
    import tempfile
    import urllib.request

    from app.oss_uploader import OssUploader
    from app.pipeline.image_pipeline import (
        process_local_images,
        safe_name,
        upload_processed_to_oss,
    )

    if uploader is None:
        try:
            uploader = OssUploader.from_settings()
        except Exception as exc:  # noqa: BLE001 - only fatal if we actually need to upload
            log.warning("OSS uploader not configured (existing manifests still advanced): %s", exc)

    stmt = select(MigrationItem).where(MigrationItem.status == ItemStatus.PREPARED)
    if batch_id is not None:
        stmt = stmt.where(MigrationItem.batch_id == batch_id)

    processed = skipped = 0
    for item in session.execute(stmt).scalars().all():
        if item.oss_images_json:
            item.status = ItemStatus.IMAGES_PROCESSED
            processed += 1
            continue
        src_urls = item.images_json or []
        if not src_urls:
            skipped += 1
            continue

        slug = safe_name(item.offer_id) or f"prod{item.ozon_product_id}"
        if uploader is None:
            skipped += 1
            continue
        tmpdir = tempfile.mkdtemp(prefix=f"mvimg-{slug}-")
        local_srcs: list[str] = []
        for idx, url in enumerate(src_urls[:15], start=1):
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            dst = os.path.join(tmpdir, f"src-{idx:02d}.jpg")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                with open(dst, "wb") as fh:
                    fh.write(data)
                local_srcs.append(dst)
            except Exception as exc:  # noqa: BLE001
                log.warning("image download failed %s: %s", url, exc)

        if not local_srcs:
            skipped += 1
            continue

        processed_dir = os.path.join(tmpdir, "out")
        norm = process_local_images(local_srcs, processed_dir, offer_id=item.offer_id)
        key_prefix = f"mvideo-erp/{datetime.utcnow():%Y%m%d}/{slug}"
        manifest = upload_processed_to_oss(uploader, norm, key_prefix)
        if not manifest:
            skipped += 1
            continue
        item.oss_images_json = manifest
        item.status = ItemStatus.IMAGES_PROCESSED
        processed += 1
    session.commit()
    return {"images_processed": processed, "skipped": skipped}


# --------------------------------------------------------------------------- #
# Stage 4: template_built (build the .xlsx row payload)
# --------------------------------------------------------------------------- #
def build_templates(session, *, batch_id: int | None = None) -> dict:
    """Build the filled template rows for IMAGES_PROCESSED items."""
    stmt = select(MigrationItem).where(MigrationItem.status == ItemStatus.IMAGES_PROCESSED)
    if batch_id is not None:
        stmt = stmt.where(MigrationItem.batch_id == batch_id)
    items = session.execute(stmt).scalars().all()

    rows = build_template_rows(items)
    built = 0
    for item in items:
        item.status = ItemStatus.TEMPLATE_BUILT
        built += 1
    session.commit()
    log.info("built %d template rows", built)
    return {"template_built": built, "rows": len(rows)}


# --------------------------------------------------------------------------- #
# Stage 5: mark_uploaded (external Excel upload is a manual/web action)
# --------------------------------------------------------------------------- #
def mark_uploaded(session, batch_id: int, upload_ref: str) -> dict:
    """Flag TEMPLATE_BUILT rows as uploaded (upload-history reference recorded).

    The actual Excel POST to /mpa/products/import is an external web action
    (not yet automated); this only bookkeeps that the upload happened and
    records the M.Video upload-history id in ``upload_ref``.
    """
    if not str(upload_ref or "").strip():
        raise ValueError("upload_ref is required")
    stmt = (
        select(MigrationItem)
        .where(MigrationItem.batch_id == batch_id)
        .where(MigrationItem.status == ItemStatus.TEMPLATE_BUILT)
    )
    uploaded = 0
    for item in session.execute(stmt).scalars().all():
        item.upload_ref = str(upload_ref)
        item.status = ItemStatus.TEMPLATE_UPLOADED
        uploaded += 1
    session.commit()
    return {"template_uploaded": uploaded, "upload_ref": str(upload_ref)}


# --------------------------------------------------------------------------- #
# Stage 6: poll mappings (offer_id -> product_id) via OMNI
# --------------------------------------------------------------------------- #
def poll_mappings(session, omni, *, batch_id: int | None = None) -> dict:
    """Resolve product_id for TEMPLATE_UPLOADED / MAPPING_PENDING rows.

    Read-only: one OMNI mapping/list page-set filtered to our offer_ids.
    Rows whose offer_id is returned become PRODUCT_MATCHED (product_id stored
    in mv_material_id); rows not yet seen stay MAPPING_PENDING (still uploading).
    """
    stmt = select(MigrationItem).where(
        MigrationItem.status.in_(
            [ItemStatus.TEMPLATE_UPLOADED, ItemStatus.MAPPING_PENDING]
        )
    )
    if batch_id is not None:
        stmt = stmt.where(MigrationItem.batch_id == batch_id)
    items = session.execute(stmt).scalars().all()
    if not items:
        return {"product_matched": 0, "mapping_pending": 0}

    offer_ids = [str(it.offer_id) for it in items if it.offer_id]
    offer_to_product: dict[str, str] = {}
    try:
        for m in omni.iter_mappings({"offer_id": offer_ids, "is_archived": False}):
            oid = str(m.get("offer_id", "") or "")
            pid = m.get("product_id")
            if oid and pid:
                offer_to_product[oid] = str(pid)
    except Exception as exc:  # noqa: BLE001 - read probe must not crash poller
        log.warning("mapping poll failed: %s", exc)
        session.rollback()
        return {"product_matched": 0, "mapping_pending": len(items)}

    matched = pending = 0
    for item in items:
        pid = offer_to_product.get(str(item.offer_id))
        if pid:
            item.mv_product_id = pid  # OMNI product_id (v0.3.2)
            item.mv_material_id = pid
            item.status = ItemStatus.PRODUCT_MATCHED
            matched += 1
        else:
            item.status = ItemStatus.MAPPING_PENDING
            pending += 1
    session.commit()
    return {"product_matched": matched, "mapping_pending": pending}


# --------------------------------------------------------------------------- #
# Stage 7: apply price + stock via OMNI (RUB)
# --------------------------------------------------------------------------- #
def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def apply_price_stock(
    session,
    omni,
    *,
    batch_id: int | None = None,
    dry_run: bool = True,
) -> dict:
    """Push OMNI price/update then stock/update for PRODUCT_MATCHED rows.

    dry_run=True (default): only report how many rows WOULD be pushed; no state
    changes, no OMNI writes. dry_run=False actually calls omni.price_update /
    omni.stock_update and advances PRODUCT_MATCHED -> PRICED -> STOCKED.
    Prices are converted CNY(item.price_rub) -> RUB via build_price_item.
    """
    settings = get_settings()
    stmt = select(MigrationItem).where(MigrationItem.status == ItemStatus.PRODUCT_MATCHED)
    if batch_id is not None:
        stmt = stmt.where(MigrationItem.batch_id == batch_id)
    items = list(session.execute(stmt).scalars().all())
    if not items:
        return {"priced": 0, "stocked": 0, "failed": 0, "would_price": 0, "would_stock": 0}

    report = {"would_price": len(items), "would_stock": len(items)}
    if dry_run:
        log.info("dry-run: would price/stock %d rows (no OMNI write)", len(items))
        report.update({"priced": 0, "stocked": 0, "failed": 0})
        return report

    priced = stocked = failed = 0
    for chunk in _chunks(items, 500):
        price_items = [
            build_price_item(
                it.offer_id,
                it.price_rub,
                product_id=it.mv_product_id or it.offer_id,
            )
            for it in chunk
        ]
        stock_items = [
            build_stock_item(
                it.offer_id,
                int(it.stock if it.stock is not None else settings.default_stock),
                product_id=it.mv_product_id or it.offer_id,
                location_id=it.mv_warehouse_code or settings.mv_warehouse_code,
            )
            for it in chunk
        ]
        try:
            resp = omni.price_update(price_items, currency="RUB")
            failed_list = (resp or {}).get("failed") or []
            if failed_list:
                raise RuntimeError(f"price rejected {len(failed_list)} items")
            for it in chunk:
                it.status = ItemStatus.PRICED
                it.price_set = True
            priced += len(chunk)
            session.commit()

            resp = omni.stock_update(stock_items)
            failed_list = (resp or {}).get("failed") or []
            if failed_list:
                raise RuntimeError(f"stock rejected {len(failed_list)} items")
            for it in chunk:
                it.status = ItemStatus.STOCKED
                it.stock_set = True
            stocked += len(chunk)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            for it in chunk:
                it.status = ItemStatus.NEEDS_REVIEW
                it.last_error = f"omni price/stock: {exc}"
                failed += 1
            session.commit()
    report.update({"priced": priced, "stocked": stocked, "failed": failed})
    return report


# --------------------------------------------------------------------------- #
# One-shot runner (v0.3): pull -> prepare -> images -> template -> reconcile
# --------------------------------------------------------------------------- #
def run_once(
    db,
    ozon,
    omni,
    *,
    uploader=None,
    limit: int | None = None,
    batch_ref: str | None = None,
    note: str = "",
    do_upload: bool = False,
) -> dict:
    """Run the safe, no-external-write portion of the v0.3 pipeline.

    Stops at ``template_built`` by default (do_upload=False). It does NOT poll
    mappings or push price/stock: those are read/write stages driven by the
    scheduler / explicit CLI. The Excel upload itself is a manual web action;
    when ``do_upload=True`` it only logs the TODO hook (no real external POST).
    """
    batch = pull_ozon_products(db, ozon, limit=limit, batch_ref=batch_ref, note=note)
    prepare = run_prepare(db, batch_id=batch.id)
    images = run_images(db, uploader=uploader, batch_id=batch.id)
    templates = build_templates(db, batch_id=batch.id)

    if do_upload:
        # TODO: Excel upload to /mpa/products/import is a browser/web action;
        # not automated yet. mark_uploaded() must be called manually once the
        # upload-history id is known. No real external request is made here.
        log.info("do_upload=True but Excel upload automation is not implemented yet")

    summary = reconcile_batch(db, batch)
    summary["stages"] = {"prepare": prepare, "images": images, "templates": templates}
    batch.status = BatchStatus.DONE if summary["consistent"] else BatchStatus.FAILED
    db.commit()
    return summary


# =========================================================================== #
# DEPRECATED v0.2 pipeline (traditional MaterialV2 create -> taskStatus poll)
# --------------------------------------------------------------------------- #
# These are kept ONLY so old rows / callers still import. The traditional API
# returns API_KEY_INTERNAL_NOT_CONTAINS_KEY_TYPE for this account, so the v0.3
# pipeline does NOT call them. Do NOT delete; do NOT wire into run_once.
# =========================================================================== #
def run_submit(session, mvideo, *, batch_id: int | None = None) -> dict:
    """DEPRECATED: old MaterialV2 create (traditional API, no permission)."""
    raise NotImplementedError(
        "run_submit() is DEPRECATED (traditional API MaterialV2 has no permission "
        "for this account); use the Excel-template upload + OMNI pipeline instead."
    )


def poll_moderation(session, mvideo, *, batch_id: int | None = None) -> dict:
    """DEPRECATED: old taskStatus moderation poll (traditional API)."""
    raise NotImplementedError(
        "poll_moderation() is DEPRECATED; use poll_mappings(omni) instead."
    )


# legacy status constants retained for parsing old rows (not written by v0.3)
__all__ = [
    "pull_ozon_products",
    "run_prepare",
    "run_images",
    "build_templates",
    "mark_uploaded",
    "poll_mappings",
    "apply_price_stock",
    "run_once",
    "run_submit",
    "poll_moderation",
    "LegacyMaterialStatus",
]
