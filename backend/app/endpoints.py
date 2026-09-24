"""M.Video traditional API endpoint registry — VERIFIED against live OpenAPI.

v0.2 (2026-09-18): replaced every ``# VERIFY`` placeholder with the real
endpoint paths, auth header and rate-limit groups taken from the live OpenAPI
spec at https://api.sellers.mvideo.ru/openapi/api/main (v1.5.9, fetched from
the logged-in ЛК on 2026-09-18). No more placeholders remain for the core
workflow; only the FBS reserve/supply sub-resources (documented, not yet
exercised by the migration) are listed for completeness.

Auth (per spec): every operation uses the ``Api-Key`` security scheme — the
API key is sent as a plain header named ``Api-Key`` (no prefix).
Rate limits (per spec, 3h sliding window, 5-min block on breach):
  /v2/price    POST,PUT,PATCH,DELETE -> 300  req / 3h
  /v2/stock    POST,PUT,PATCH,DELETE -> 300  req / 3h
  /v2/material POST,PUT,PATCH,DELETE -> 1000 req / 3h
  /v2/material/info POST             -> 1000 req / 3h
  /v2/dictionaries/attribute GET     -> 1000 req / 3h
  /v2/readstock GET                   -> (no explicit limit in spec)
  /v2/task/*   GET                    -> (no explicit limit in spec)
The client only ever reads from this module, so any future spec change is
contained to this one file.
"""

from __future__ import annotations

# Header used to send the API key (spec: Api-Key security scheme, header, no prefix).
AUTH_HEADER_NAME = "Api-Key"
AUTH_HEADER_PREFIX = ""

# Path templates. {base} is prepended by the client (api.sellers.mvideo.ru).
ENDPOINTS: dict[str, dict[str, str]] = {
    # DictionaryV2 (GET)
    "dict.categories":       {"method": "GET", "path": "/v2/dictionaries/category"},
    "dict.attributes":       {"method": "GET", "path": "/v2/dictionaries/attribute"},
    "dict.attribute_values": {"method": "POST", "path": "/v2/dictionaries/attributeValues"},
    "dict.types":            {"method": "GET", "path": "/v2/dictionaries/typeProducts"},
    # MaterialV2 (goods)
    "material.create":       {"method": "POST", "path": "/v2/material"},
    "material.status":       {"method": "GET", "path": "/v2/material/{taskCode}/status"},
    "material.list":         {"method": "POST", "path": "/v2/material/info"},
    # PriceV2
    "price.update":          {"method": "POST", "path": "/v2/price"},
    # StockV2
    "stock.update":          {"method": "POST", "path": "/v2/stock"},
    "stock.list":            {"method": "GET", "path": "/v2/readstock"},
    # TaskV2
    "task.info":             {"method": "GET", "path": "/v2/task/{id}"},
    "task.errors":           {"method": "GET", "path": "/v2/task/{id}/errors"},
    "task.progress":         {"method": "GET", "path": "/v2/task/{id}/progress"},
    # LinkageV2 (multi-SKU)
    "linkage.upsert":        {"method": "POST", "path": "/v2/linkage/operations"},
    "linkage.status":        {"method": "GET", "path": "/v2/linkage/{taskCode}/status"},
    "linkage.list":          {"method": "POST", "path": "/v2/linkage/info"},
    # Connection check
    "check.connection":      {"method": "GET", "path": "/v2/checking-connection"},
}

# Rate-limit groups: name -> (requests, window_seconds). 3h window, block 5 min.
RATE_LIMIT_GROUPS: dict[str, tuple[int, int]] = {
    "MaterialV2": (1000, 3 * 3600),
    "PriceV2":    (300, 3 * 3600),
    "StockV2":    (300, 3 * 3600),
    "LinkageV2":  (1000, 3 * 3600),
    "DictionaryV2": (1000, 3 * 3600),
    "TaskV2":     (300, 3 * 3600),  # not limited per spec; conservative default
    "Other":      (1000, 3 * 3600),
}

# Map an endpoint key to its rate-limit group name.
def group_of(endpoint_key: str) -> str:
    head = endpoint_key.split(".", 1)[0]
    return {
        "dict": "DictionaryV2",
        "material": "MaterialV2",
        "price": "PriceV2",
        "stock": "StockV2",
        "task": "TaskV2",
        "linkage": "LinkageV2",
        "check": "Other",
    }.get(head, "Other")
