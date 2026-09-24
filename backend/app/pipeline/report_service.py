"""Batch report + read-back reconciliation (v0.4.0).

Two pure-ish helpers that operate on an open SQLAlchemy session / an OMNI
client:

``batch_report(session, batch_id)``
    Aggregate per-status counts, totals, how many items have been mapped to
    an OMNI product_id, how many have price/stock actually set, and a detail
    list of every ``needs_review`` row (offer_id + last_error). This is the
    single "where are we?" view shown by ``/api/report/{batch_id}`` and the
    ``continue_batch.py`` CLI.

``readback_verify(omni, items, *, rate=None, default_stock=None,
                  warehouse_location=None)``
    For items that already have ``mv_product_id`` resolved, call OMNI
    ``price_info`` / ``stock_info`` and compare the remote values against our
    local expectations. Prices are compared in KOPECKS (RUB * 100); the local
    ``price_rub`` field holds the CNY source price, so we convert via
    ``cny_to_rub`` before comparing. A tolerance of 100 kopecks (1 RUB) is
    allowed because M.Video truncates pushed prices to whole rubles
    (see CHANGELOG v0.3.2: 1438.80 -> 1438.00).
"""

from __future__ import annotations

import logging
from collections import Counter
from decimal import Decimal

from sqlalchemy import select

from ..config import get_settings
from ..currency import cny_to_rub
from ..models import ItemStatus, MigrationBatch, MigrationItem

log = logging.getLogger("mvideo.report")

# Tolerance for price read-back: M.Video truncates to whole rubles on its side
# (143880 kopecks pushed -> 143800 read back). Allow up to 1 RUB (100 kopecks).
_PRICE_TOLERANCE_KOPECKS = 100


# --------------------------------------------------------------------------- #
# batch_report
# --------------------------------------------------------------------------- #
def batch_report(session, batch_id: int) -> dict:
    """Aggregate status / progress / needs_review detail for one batch."""
    batch = session.get(MigrationBatch, batch_id)
    if batch is None:
        raise LookupError(f"batch {batch_id} not found")

    items = list(
        session.execute(
            select(MigrationItem).where(MigrationItem.batch_id == batch_id)
        ).scalars().all()
    )

    counts: Counter[str] = Counter(it.status for it in items)

    total_price = Decimal("0")
    mapped_product = 0
    priced_set = 0
    stocked_set = 0
    needs_review: list[dict] = []

    for it in items:
        try:
            total_price += Decimal(str(it.price_rub or 0))
        except Exception:  # noqa: BLE001
            pass
        if (it.mv_product_id or "").strip():
            mapped_product += 1
        if it.price_set:
            priced_set += 1
        if it.stock_set:
            stocked_set += 1
        if it.status == ItemStatus.NEEDS_REVIEW:
            needs_review.append({
                "item_id": it.id,
                "offer_id": it.offer_id,
                "name": it.name,
                "last_error": it.last_error,
            })

    return {
        "batch_id": batch.id,
        "batch_ref": batch.batch_ref,
        "status": batch.status,
        "total_count": len(items),
        "by_status": dict(counts),
        "mapped_product_id": mapped_product,
        "priced": priced_set,
        "stocked": stocked_set,
        "needs_review_count": len(needs_review),
        "needs_review": needs_review,
        "total_price_cny_source": float(total_price),
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
    }


# --------------------------------------------------------------------------- #
# readback_verify
# --------------------------------------------------------------------------- #
def _expected_kopecks(item, rate) -> int:
    """Local CNY price -> expected OMNI kopecks (v0.6.3: CNY * 1.1 * RATE * 100)."""
    rub = cny_to_rub(item.price_rub or 0, rate)
    from ..currency import PRICE_MARKUP
    rub_markup = (rub * PRICE_MARKUP).quantize(Decimal("0.01"))
    return int((rub_markup * Decimal("100")).to_integral_value())


def _extract_price_map(resp: dict) -> dict[str, int]:
    """Build {product_id(str): price_in_kopecks(int)} from a price/info response."""
    out: dict[str, int] = {}
    if not isinstance(resp, dict):
        return out
    for key in ("prices", "result", "items"):
        rows = resp.get(key)
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("product_id", "") or "")
                price = row.get("price")
                if pid and price is not None:
                    try:
                        out[pid] = int(price)
                    except (TypeError, ValueError):
                        pass
            if out:
                return out
    return out


def _extract_stock_map(resp: dict) -> dict[str, int]:
    """Build {product_id(str): total_count(int)} from a stock/info response.

    Sums across all location_ids returned for one product (the seller typically
    pushes to a single R-объект, but we sum to be safe).
    """
    out: dict[str, int] = {}
    if not isinstance(resp, dict):
        return out
    for key in ("stocks", "result", "items"):
        rows = resp.get(key)
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("product_id", "") or "")
                count = row.get("count", row.get("quantity"))
                if pid and count is not None:
                    try:
                        out[pid] = out.get(pid, 0) + int(count)
                    except (TypeError, ValueError):
                        pass
            if out:
                return out
    return out


def readback_verify(
    omni,
    items,
    *,
    rate: float | str | None = None,
    default_stock: int | None = None,
    warehouse_location: str | None = None,
) -> dict:
    """Read back price/stock from OMNI and compare to local expectations.

    Only items with a non-empty ``mv_product_id`` are considered. Returns::

        {
          "checked": n,
          "matched": [ {offer_id, product_id, price_kopecks, stock_count}, ... ],
          "mismatch": [ {offer_id, product_id, field, expected, actual, ...}, ... ],
          "missing":  [ {offer_id, product_id, reason}, ... ],
        }
    """
    st = get_settings()
    if rate is None:
        rate = st.mv_rub_rate
    if default_stock is None:
        default_stock = st.default_stock
    if warehouse_location is None:
        warehouse_location = st.mv_warehouse_code

    candidates = [it for it in items if (it.mv_product_id or "").strip()]
    if not candidates:
        return {"checked": 0, "matched": [], "mismatch": [], "missing": []}

    product_ids = [str(it.mv_product_id) for it in candidates]

    # --- price read-back (one call) ---
    try:
        price_resp = omni.price_info({"product_id": product_ids}, limit=500)
    except Exception as exc:  # noqa: BLE001 - readback must not crash caller
        log.warning("price_info readback failed: %s", exc)
        price_resp = {}
    price_map = _extract_price_map(price_resp)

    # --- stock read-back (one call) ---
    stock_filter: dict = {"product_id": product_ids}
    if warehouse_location:
        stock_filter["location_id"] = [warehouse_location]
    try:
        stock_resp = omni.stock_info(stock_filter, limit=500)
    except Exception as exc:  # noqa: BLE001
        log.warning("stock_info readback failed: %s", exc)
        stock_resp = {}
    stock_map = _extract_stock_map(stock_resp)

    matched: list[dict] = []
    mismatch: list[dict] = []
    missing: list[dict] = []

    for it in candidates:
        pid = str(it.mv_product_id)
        expected_price = _expected_kopecks(it, rate)
        from ..currency import MV_FIXED_STOCK
        expected_stock = MV_FIXED_STOCK

        remote_price = price_map.get(pid)
        remote_stock = stock_map.get(pid)

        entry = {
            "offer_id": it.offer_id,
            "product_id": pid,
        }

        # --- price check ---
        price_ok = False
        if remote_price is None:
            price_issue = "price_not_found"
        elif abs(remote_price - expected_price) <= _PRICE_TOLERANCE_KOPECKS:
            price_ok = True
            price_issue = None
        else:
            price_issue = "price_diff"

        # --- stock check ---
        stock_ok = False
        if remote_stock is None:
            stock_issue = "stock_not_found"
        elif remote_stock == expected_stock:
            stock_ok = True
            stock_issue = None
        else:
            stock_issue = "stock_diff"

        if remote_price is None and remote_stock is None:
            missing.append({**entry, "reason": "not_found_in_omni"})
        elif price_ok and stock_ok:
            matched.append({
                **entry,
                "price_kopecks": remote_price,
                "stock_count": remote_stock,
            })
        else:
            md = {**entry}
            if price_issue == "price_diff":
                md["field"] = "price"
                md["expected_kopecks"] = expected_price
                md["actual_kopecks"] = remote_price
            elif stock_issue == "stock_diff":
                md["field"] = "stock"
                md["expected_count"] = expected_stock
                md["actual_count"] = remote_stock
            elif price_issue == "price_not_found":
                md["field"] = "price"
                md["expected_kopecks"] = expected_price
                md["actual_kopecks"] = None
            elif stock_issue == "stock_not_found":
                md["field"] = "stock"
                md["expected_count"] = expected_stock
                md["actual_count"] = None
            mismatch.append(md)

    return {
        "checked": len(candidates),
        "matched": matched,
        "mismatch": mismatch,
        "missing": missing,
    }


__all__ = ["batch_report", "readback_verify"]
