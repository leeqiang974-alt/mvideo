# -*- coding: utf-8 -*-
"""Probe: dump ONE product's v4 attributes keys to find category-name field."""
import json, re
from pathlib import Path
import httpx

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
items = [x.strip() for x in raw if x.strip()]
# use xymall 2536021 block: label xymall, id 2536021, next line key
idx = items.index("2536021")
cid = "2536021"
key = items[idx+1]
h = {"Client-Id": cid, "Api-Key": key, "Content-Type": "application/json"}
with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=30) as cli:
    r = cli.post("/v3/product/list", json={"filter": {"visibility": "ALL"}, "limit": 3})
    pids = [x["product_id"] for x in r.json()["result"]["items"]]
    r2 = cli.post("/v4/product/info/attributes",
                  json={"filter": {"product_id": pids, "visibility": "ALL"}, "limit": 10})
    data = r2.json()
res = data.get("result", [])
print("num:", len(res))
if res:
    p = res[0]
    print("TOP-LEVEL KEYS:", sorted(p.keys()))
    for k in ("id", "name", "offer_id", "description_category_id", "description_category_name",
              "type_id", "type_name", "category"):
        print("  ", k, "=", str(p.get(k))[:120])
    # price info lives elsewhere; dump one attr sample
    atts = p.get("attributes", [])
    print("n_attributes:", len(atts))
    for a in atts[:8]:
        print("   attr:", str(a)[:160])
