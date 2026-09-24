"""OMNI API (omni-net) endpoint registry — v0.3 primary channel.

Paths confirmed against D:\\Desktop\\mvideo\\_work\\omninet_api_doc.txt (crawled 2026-09).
Auth: header ``api-key`` whose value is the same MVIDEO_API_KEY secret.
Rate limit: POST/PUT/PATCH/DELETE under /v1/product and /v1/order = 300 / 3 h,
exceed -> 5 min ban (handled by app.ratelimit.RequestBudgeter).
"""

from __future__ import annotations

# Header name carrying the key (per doc AUTHORIZATIONS: api-key).
OMNI_AUTH_HEADER = "api-key"

# Sliding-window budget groups (matches the doc's two limited URL prefixes).
RATE_LIMIT_GROUPS = {"/v1/product", "/v1/order"}

# endpoint_key -> path (all POST unless noted).
PATHS: dict[str, str] = {
    # prices
    "price.update": "/v1/product/price/update",
    "price.info":   "/v1/product/price/info",
    # stock
    "stock.update": "/v1/product/stock/update",
    "stock.info":   "/v1/product/stock/info",
    # product identity mapping (offer_id <-> product_id)
    "mapping.list": "/v1/product/mapping/list",
    # FBS marketplaces locations
    "market.location.list": "/v1/market/location/list",
    # merchant (seller) warehouses
    "merchant.location.update":  "/v1/merchant/location/update",
    "merchant.location.list":    "/v1/merchant/location/list",
    "merchant.location.create":  "/v1/merchant/location/create",
    "merchant.location.archive": "/v1/merchant/location/archive",
    # FBS orders
    "order.fbs.status.update": "/v1/order/fbs/status/update",
    "order.fbs.list":           "/v1/order/fbs/list",
    "order.fbs.cancel":         "/v1/order/fbs/cancel",
    "order.fbs.labels.get":     "/v1/order/fbs/labels/get",
    # shipments
    "shipment.update":        "/v1/shipment/update",
    "shipment.pass.update":   "/v1/shipment/pass/update",
    "shipment.get":           "/v1/shipment/get",
    "shipment.fbs.status.update": "/v1/shipment/fbs/status/update",
    "shipment.create":        "/v1/shipment/create",
    "shipment.cancel":        "/v1/shipment/cancel",
    # labels
    "label.fbs.shipment.get": "/v1/label/fbs/shipment/get",
    "label.fbs.packages.get": "/v1/label/fbs/packages/get",
}


def budget_group(path: str) -> str:
    """Map a path to its rate-limit prefix (/v1/product or /v1/order)."""
    if path.startswith("/v1/product"):
        return "/v1/product"
    if path.startswith("/v1/order"):
        return "/v1/order"
    return "other"
