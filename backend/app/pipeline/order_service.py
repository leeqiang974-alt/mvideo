"""Read-only FBS order view (v0.4.0).

Wraps ``omni.order_fbs_list`` into a small, normalised dict so the API / CLI
can show the seller's incoming FBS orders without ever mutating them. This
module deliberately does NOT call ``order_fbs_status_update`` or
``order_fbs_cancel`` — order lifecycle changes are a separate, riskier workflow
and stay manual for now.

Public functions:
  list_fbs_orders(omni, body=None, limit=100) -> dict
      {"orders": [...], "total": int, "raw_keys": [...]}
  summarize_orders(orders) -> dict
      {"by_status": {status: count}, "total": n}
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _extract_orders(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort extraction of the order list from an OMNI response.

    The OMNI contract names are snake_case; we accept a few common shapes
    (``orders`` / ``result`` / ``items``) so we are robust to schema drift.
    """
    if not isinstance(resp, dict):
        return []
    for key in ("orders", "result", "items", "data"):
        val = resp.get(key)
        if isinstance(val, list):
            return [o for o in val if isinstance(o, dict)]
    # fall back: any top-level list value of dicts
    for val in resp.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return list(val)
    return []


def list_fbs_orders(
    omni,
    body: dict[str, Any] | None = None,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """Return a normalised view of FBS orders.

    Parameters
    ----------
    omni:
        An ``OmniClient`` (or any object exposing ``order_fbs_list(body,
        limit=...)``). Read-only.
    body:
        Optional filter/cursor payload forwarded to OMNI as-is.
    limit:
        Per-page size (default 100).

    Returns
    -------
    dict
        ``{"orders": [order_dict, ...], "total": int, "next_cursor": str|None}``
        On any OMNI error the function returns ``{"orders": [], "total": 0,
        "error": str}`` rather than raising — the API route must not 500.
    """
    try:
        resp = omni.order_fbs_list(body or {}, limit=limit)
    except Exception as exc:  # noqa: BLE001 - read probe must not crash
        return {"orders": [], "total": 0, "next_cursor": None, "error": str(exc)}

    if not isinstance(resp, dict):
        return {"orders": [], "total": 0, "next_cursor": None}

    orders = _extract_orders(resp)
    total = resp.get("total")
    if not isinstance(total, int):
        total = len(orders)
    next_cursor = resp.get("next_cursor") or None
    return {"orders": orders, "total": int(total), "next_cursor": next_cursor}


def summarize_orders(orders: list[dict[str, Any]]) -> dict[str, Any]:
    """Count orders by their ``status`` field (best-effort)."""
    counter: Counter[str] = Counter()
    for o in orders or []:
        status = str(o.get("status", "") or o.get("order_status", "") or "unknown")
        counter[status] += 1
    return {"by_status": dict(counter), "total": len(orders or [])}


__all__ = ["list_fbs_orders", "summarize_orders"]
