# -*- coding: utf-8 -*-
"""Precise OMNI auth probe: isolate header style vs key-type permission."""
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://omni-net.sellers.mvideo.ru"

def load_key():
    with open(r"C:\MvideoERP\.env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("MVIDEO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

KEY = load_key()
print("key loaded:", bool(KEY), "len:", len(KEY) if KEY else 0)

def post(url, body, headers_extra=None, timeout=20):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers_extra:
        for k, v in headers_extra.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:300]
    except Exception as e:
        return "ERR", repr(e)[:300]

HEADER_VARIANTS = [
    ("api-key", KEY),          # doc literal
    ("Api-Key", KEY),          # capitalized like legacy
    ("X-API-KEY", KEY),
    ("api-key", "Key " + KEY), # prefixed variant
]

# A) mapping/list with full body, all header variants
print("=== A) /v1/product/mapping/list (full body) ===")
body_ml = {"filter": {"product_id": [], "offer_id": [], "is_archived": False}, "cursor": "", "limit": 5}
for hn, hv in HEADER_VARIANTS:
    st, b = post(BASE + "/v1/product/mapping/list", body_ml, {hn: hv})
    print(f"  {hn}: {st}  {b[:150]}")

# B) stock/info full body
print("=== B) /v1/product/stock/info (full body) ===")
body_si = {"filter": {"product_id": [], "offer_id": [], "location_id": [], "is_archived": False}, "cursor": "", "limit": 5}
for hn, hv in HEADER_VARIANTS:
    st, b = post(BASE + "/v1/product/stock/info", body_si, {hn: hv})
    print(f"  {hn}: {st}  {b[:150]}")

# C) price/info full body — confirm it actually reaches 200 (auth truly ok?)
print("=== C) /v1/product/price/info (full body) ===")
body_pi = {"filter": {"product_id": [], "offer_id": []}, "cursor": "", "limit": 5}
for hn, hv in HEADER_VARIANTS:
    st, b = post(BASE + "/v1/product/price/info", body_pi, {hn: hv})
    print(f"  {hn}: {st}  {b[:150]}")

# D) price/update & stock/update empty-body (write endpoints, auth probe only; empty items = no real write)
print("=== D) write endpoints empty-body auth probe ===")
st, b = post(BASE + "/v1/product/price/update", {"items": [], "currency": "RUB"}, {"api-key": KEY})
print(f"  price/update: {st}  {b[:150]}")
st, b = post(BASE + "/v1/product/stock/update", {"items": []}, {"api-key": KEY})
print(f"  stock/update: {st}  {b[:150]}")
