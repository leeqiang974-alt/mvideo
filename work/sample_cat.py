# -*- coding: utf-8 -*-
"""Sample products in Ozon category 17027899 (the dominant 72% category)."""
import json, re
from pathlib import Path
import httpx

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
items = [x.strip() for x in raw if x.strip()]
i = items.index("2536021")
cid, key = "2536021", items[i+1]
h = {"Client-Id": cid, "Api-Key": key, "Content-Type": "application/json"}
OUT = Path(r"C:\MvideoERP\work\cat_17027899_sample.json")

with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=40) as cli:
    # tree names
    tr = cli.post("/v1/description-category/tree", json={}).json()
    names = {}
    def walk(nodes):
        for n in nodes or []:
            names[str(n.get("description_category_id"))] = n.get("category_name")
            walk(n.get("type", []))
    walk(tr.get("result", []))
    # gather products
    pids, last = [], ""
    while len(pids) < 400:
        r = cli.post("/v3/product/list", json={"filter": {"visibility": "ALL"}, "limit": 100, "last_id": last}).json()
        res = r.get("result", {})
        pids += [x["product_id"] for x in res.get("items", [])]
        last = res.get("last_id", "")
        if not last: break
    # get attributes, keep those in 17027899
    kept = []
    for j in range(0, len(pids), 100):
        chunk = pids[j:j+100]
        r = cli.post("/v4/product/info/attributes",
                     json={"filter": {"product_id": chunk, "visibility": "ALL"}, "limit": 1000}).json()
        for it in r.get("result", []):
            if str(it.get("description_category_id")) == "17027899":
                kept.append({
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "offer_id": it.get("offer_id"),
                    "type_id": it.get("type_id"),
                    "primary_image": it.get("primary_image"),
                })
        if len(kept) >= 12: break
    out = {"tree_has_17027899_name": names.get("17027899"),
           "num_tree_nodes": len(names), "samples": kept}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("name:", names.get("17027899"))
    print("tree nodes:", len(names))
    for k in kept[:12]:
        print(" -", k["name"][:80])
