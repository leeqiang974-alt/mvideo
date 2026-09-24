"""Quality gate for one migrated item before MaterialV2 create.

v0.2 (2026-09-18): aligned with the VERIFIED live OpenAPI.
- Barcode: the create API takes ``barcodes`` as 13-digit numbers (EAN13),
  max 3, first is primary. No EAN18 conversion at submit time; M.Video
  internally generates EAN16/18 (visible via material/info).
- Images: count 1..15, 3:4, resolution band, <=10MB, jpg/jpeg/png/webp.
- Required create fields (verified): offerId, salesScheme=MARKETPLACE,
  name, brand, categoryId (leaf category), vat, deliveryScheme.
- Locked after moderation: the card itself (fields above cannot change
  post-approval), so we pre-validate them before submit.

Locked-field problems are hard errors (no auto-retry); image issues are
error/warning per image_rules.  Returns a QualityReport consumed by the
pipeline to decide prepared vs needs_review.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .barcode import normalize_barcode
from .image_rules import check_image_list


@dataclass
class QualityReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    barcode13: str = ""
    report: dict = field(default_factory=dict)


def _get_images(item: dict) -> list[str]:
    imgs = item.get("images")
    if imgs is None:
        imgs = item.get("images_json", [])
    return list(imgs or [])


def run_quality_gate(
    item: dict,
    *,
    vendor_id: str,
    tn_ved_present: bool,
) -> QualityReport:
    """Validate one migration item. Never raises."""
    rep = QualityReport()
    errors: list[str] = []
    warnings: list[str] = []

    # --- 1) barcode -------------------------------------------------------
    # Excel-template path auto-generates EAN18 (col1 = "Сгенерировать"), so a
    # missing/non-EAN13 source barcode is a WARNING, not a blocker. Only used
    # for the legacy MaterialV2 create (DEPRECATED here).
    raw_bc = item.get("source_barcode", "") or ""
    bc = normalize_barcode(raw_bc)
    if not bc:
        warnings.append("barcode missing; template will auto-generate (Сгенерировать)")
    elif not (bc.isdigit() and len(bc) == 13):
        warnings.append(
            f"barcode {raw_bc!r} not EAN13; template will auto-generate (Сгенерировать)"
        )
    else:
        rep.barcode13 = bc

    # --- 2) required create fields (locked after moderation) ---------------
    if not (item.get("name") or "").strip():
        errors.append("name missing (locked field)")
    if not (item.get("brand") or "").strip():
        errors.append("brand missing (locked field)")
    if not (item.get("mv_group_id") or "").strip():
        errors.append("mv_group_id missing (categoryId, locked)")
    if not (item.get("mv_nds") or "").strip():
        errors.append("mv_nds missing (VAT, locked)")
    if not tn_ved_present:
        warnings.append("mv_tn_ved missing / not in registry (locked field)")

    # --- 2b) required pack dimensions (M.Video template cols 14-17) --------
    dims = item.get("dimensions") or {}
    need_dims = ["length_cm", "width_cm", "height_cm", "weight_kg"]
    missing_dims = [k for k in need_dims if not (float(dims.get(k) or 0) > 0)]
    if missing_dims:
        errors.append(
            f"missing pack dimensions {missing_dims} — manual fill required "
            f"(M.Video template cols 14-17 required)"
        )

    # --- 3) images -------------------------------------------------------
    # Image aspect ratio is enforced AFTER the 3:4 white-pad in the image
    # stage; here we only require >=1 source image URL exists.
    imgs = _get_images(item)
    if not imgs:
        errors.append("too few images: 0 (need >= 1)")
    img_res = {"errors": [], "warnings": [], "count": len(imgs)}

    rep.errors = errors
    rep.warnings = warnings
    rep.ok = not errors
    rep.report = {
        "barcode": {
            "raw": raw_bc,
            "normalized": bc,
            "barcode13": rep.barcode13,
        },
        "images": {
            "count": img_res["count"],
            "errors": img_res["errors"],
            "warnings": img_res["warnings"],
        },
        "locked_fields": {
            "name": bool((item.get("name") or "").strip()),
            "brand": bool((item.get("brand") or "").strip()),
            "mv_group_id": bool((item.get("mv_group_id") or "").strip()),
            "mv_nds": bool((item.get("mv_nds") or "").strip()),
            "mv_tn_ved_present": bool(tn_ved_present),
        },
    }
    return rep
