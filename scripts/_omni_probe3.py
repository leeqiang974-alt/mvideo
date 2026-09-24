# -*- coding: utf-8 -*-
"""OMNI probe WITH User-Agent header (key insight from SelSup article)."""
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
print("key len:", len(KEY) if KEY else 0)

UA_VARIANTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "doubao-erp/1.0 (M.Video ERP integration)",
    "Python-urllib/3.11",
]

def post(url, body, ua, key=KEY, timeout=20):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", ua)
    req.add_header("api-key", key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:300]
    except Exception as e:
        return "ERR", repr(e)[:300]

body = {"filter": {"product_id": [], "offer_id": []}, "cursor": "", "limit": 5}
for ua in UA_VARIANTS:
    print(f"--- UA: {ua[:60]} ---")
    st, b = post(BASE + "/v1/product/price/info", body, ua)
    print(f"  price/info: {st}  {b[:200]}")
    st, b = post(BASE + "/v1/product/mapping/list", {"filter": {"product_id": [], "offer_id": [], "is_archived": False}, "cursor": "", "limit": 5}, ua)
    print(f"  mapping/list: {st}  {b[:200]}")
