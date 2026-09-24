# -*- coding: utf-8 -*-
"""Push price/stock for the approved 5 brooch products and read back.
Runs on laptop (has OMNI key in .env + Ozon creds)."""
import json, os, re
from pathlib import Path
import httpx

ENV = Path(r"C:\MvideoERP\.env")
env = {}
for line in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
OMNI_KEY = env.get("OMNI_API_KEY", "")
print("omni key present:", bool(OMNI_KEY))

# Ozon creds (xymall)
CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
items = [x.strip() for x in CRED.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
i = items.index("2536021"); OZON_KEY = items[i+1]
OZON_CID = "2536021"

PILOT = json.loads(Path(r"C:\MvideoERP\work\brooch_pilot.json").read_text(encoding="utf-8"))
offer_ids = [p["offer_id"] for p in PILOT]
ozon_ids = [p["ozon_id"] for p in PILOT]
print("offers:", offer_ids)

# 1) mapping offer_id -> product_id
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",
                  headers={"api-key": OMNI_KEY, "Content-Type": "application/json"}, timeout=30) as om:
    r = om.post("/v1/product/mapping/list", json={"filter": {"offer_id": offer_ids}, "limit": 100})
    print("mapping HTTP", r.status_code)
    mappings = r.json().get("mappings", [])
    oid2pid = {m.get("offer_id"): m.get("product_id") for m in mappings}
    print("product_ids:", oid2pid)

# 2) Ozon prices via v3 info/list (price is a top-level string field)
prices = {}
with httpx.Client(base_url="https://api-seller.ozon.ru",
                  headers={"Client-Id": OZON_CID, "Api-Key": OZON_KEY, "Content-Type": "application/json"},
                  timeout=30) as oz:
    r = oz.post("/v3/product/info/list", json={"product_id": ozon_ids, "sku": [], "offer_id": []})
    print("ozon info HTTP", r.status_code)
    for it in r.json().get("items", []):
        prices[it.get("id")] = {"price": it.get("price"), "currency": it.get("currency_code")}
print("prices:", prices)

RATE = 12.0
MARKUP = 1.1; OLD_MULT = 2
loc = 10011496
price_items, stock_items = [], []
for p in PILOT:
    pid = oid2pid.get(p["offer_id"])
    if not pid:
        print("NO PID for", p["offer_id"]); continue
    op = prices.get(p["ozon_id"], {})
    cny = float(op.get("price") or 0)
    rub = int(round(cny * RATE * MARKUP))
    old = int(round(rub * OLD_MULT))
    price_items.append({"product_id": pid, "price": rub*100, "old_price": old*100, "offer_id": p["offer_id"]})
    stock_items.append({"product_id": pid, "count": 999, "location_id": loc})
    print(f"  {p['offer_id']}: cny={cny} -> rub={rub} old={old} kopecks")

if price_items:
    with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",
                      headers={"api-key": OMNI_KEY, "Content-Type": "application/json"}, timeout=30) as om:
        pr = om.post("/v1/product/price/update", json={"items": price_items, "currency": "RUB"})
        print("price update HTTP", pr.status_code, pr.text[:300])
        sr = om.post("/v1/product/stock/update", json={"items": stock_items})
        print("stock update HTTP", sr.status_code, sr.text[:300])
