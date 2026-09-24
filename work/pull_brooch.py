# -*- coding: utf-8 -*-
"""Pull ~5 brooch-type products (type_id 87458886) from xymall with full attrs+price."""
import json, re
from pathlib import Path
import httpx

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
items = [x.strip() for x in raw if x.strip()]
i = items.index("2536021")
cid, key = "2536021", items[i+1]
h = {"Client-Id": cid, "Api-Key": key, "Content-Type": "application/json"}
OUT = Path(r"C:\MvideoERP\work\brooch_pilot.json")

def attr_map(attrs):
    m = {}
    for a in attrs:
        vals = [v.get("value", "") for v in a.get("values", [])]
        m[str(a.get("id"))] = vals[0] if vals else ""
    return m

with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=40) as cli:
    # gather pids
    pids, last = [], ""
    while len(pids) < 300:
        r = cli.post("/v3/product/list", json={"filter": {"visibility": "ALL"}, "limit": 100, "last_id": last}).json()
        res = r.get("result", {})
        pids += [x["product_id"] for x in res.get("items", [])]
        last = res.get("last_id", "")
        if not last: break
    # batch attrs, keep brooch type
    brooch_ids = []
    detailed = {}
    for j in range(0, len(pids), 100):
        chunk = pids[j:j+100]
        r = cli.post("/v4/product/info/attributes",
                     json={"filter": {"product_id": chunk, "visibility": "ALL"}, "limit": 1000}).json()
        for it in r.get("result", []):
            if str(it.get("type_id")) == "87458886":
                brooch_ids.append(it.get("id"))
                detailed[it.get("id")] = it
        if len(brooch_ids) >= 8: break
    brooch_ids = brooch_ids[:5]
    # prices
    pr = cli.post("/v3/product/info/list", json={"product_id": brooch_ids, "sku": [], "offer_id": []}).json()
    price_map = {it["id"]: it for it in pr.get("result", {}).get("items", [])}
    out = []
    for pid in brooch_ids:
        it = detailed[pid]
        am = attr_map(it.get("attributes", []))
        prinfo = price_map.get(pid, {})
        out.append({
            "ozon_id": pid,
            "name": it.get("name"),
            "offer_id": it.get("offer_id"),
            "primary_image": it.get("primary_image"),
            "images": it.get("images", []),
            "width_cm": it.get("width"), "height_cm": it.get("height"),
            "depth_cm": it.get("depth"), "weight_kg": it.get("weight"),
            "brand": am.get("85") or am.get("31"),
            "color": am.get("34") or am.get("4454"),
            "material": am.get("5534") or am.get("4386"),
            "description_html": am.get("4191", ""),
            "price_currency": (prinfo.get("price") or {}).get("currency_code"),
            "price": (prinfo.get("price") or {}).get("price"),
            "marketing_price": (prinfo.get("price") or {}).get("marketing_price"),
        })
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", len(out), "brooch products")
    for o in out:
        print(" -", o["offer_id"], "|", str(o["name"])[:50], "| price", o["price"], o["price_currency"])
