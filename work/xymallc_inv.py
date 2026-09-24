# -*- coding: utf-8 -*-
"""Test all xymallc (3815760) keys, then inventory the working one."""
import json, collections, re
from pathlib import Path
import httpx

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
items = [x.strip() for x in raw if x.strip()]
# gather all keys that follow 3815760
keys = []
for i, s in enumerate(items):
    if s == "3815760" and i+1 < len(items):
        nxt = items[i+1]
        km = re.search(r"key[：:]\s*([A-Za-z0-9_\-]+)", nxt, re.I)
        keys.append(km.group(1) if km else re.sub(r"^key[：:]\s*","",nxt,flags=re.I))
print("found", len(keys), "keys for 3815760")

working = None
for k in keys:
    h = {"Client-Id":"3815760","Api-Key":k,"Content-Type":"application/json"}
    try:
        r = httpx.post("https://api-seller.ozon.ru/v3/product/list",
                       headers=h, json={"filter":{"visibility":"ALL"},"limit":5}, timeout=20)
        print("key", k[:6]+"***", "->", r.status_code, "items:", len(r.json().get("result",{}).get("items",[])))
        if r.status_code == 200:
            working = k; break
    except Exception as e:
        print("key", k[:6]+"***", "ERR", repr(e)[:80])

if not working:
    print("NO working key for xymallc"); raise SystemExit

h = {"Client-Id":"3815760","Api-Key":working,"Content-Type":"application/json"}
with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=40) as cli:
    pids, last = [], ""
    while True:
        r = cli.post("/v3/product/list", json={"filter":{"visibility":"ALL"},"limit":100,"last_id":last}).json()
        res = r.get("result",{})
        pids += [x["product_id"] for x in res.get("items",[])]
        last = res.get("last_id","")
        if not last: break
    cc = collections.Counter()
    for j in range(0,len(pids),100):
        r = cli.post("/v4/product/info/attributes",
                     json={"filter":{"product_id":pids[j:j+100],"visibility":"ALL"},"limit":1000}).json()
        for it in r.get("result",[]):
            cc[str(it.get("description_category_id"))] += 1
    print("xymallc total:", len(pids), "cats:", len(cc))
    out = {"product_count": len(pids), "categories":[{"ozon_category_id":c,"count":n} for c,n in cc.most_common()]}
    Path(r"C:\MvideoERP\work\xymallc_inventory.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
