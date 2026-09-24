# -*- coding: utf-8 -*-
"""Pull a batch of brooch products (type 87458886) with price, excluding already-done."""
import json, re, sys
from pathlib import Path
import httpx

STORE = sys.argv[1] if len(sys.argv)>1 else "2536021"  # client id
N = int(sys.argv[2]) if len(sys.argv)>2 else 20
OUT = Path(r"C:\MvideoERP\work\brooch_batch.json")
DONE = set()
for prev in [r"C:\MvideoERP\work\brooch_pilot.json", r"C:\MvideoERP\work\brooch_batch.json"]:
    pp = Path(prev)
    if pp.exists():
        for o in json.loads(pp.read_text(encoding="utf-8")):
            DONE.add(o["offer_id"])

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
items = [x.strip() for x in raw if x.strip()]
i = items.index(STORE)
key = items[i+1]
h = {"Client-Id": STORE, "Api-Key": key, "Content-Type": "application/json"}

def amap(attrs):
    m = {}
    for a in attrs:
        vs = [v.get("value","") for v in a.get("values",[])]
        m[str(a.get("id"))] = vs[0] if vs else ""
    return m

with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=40) as cli:
    pids, last = [], ""
    while len(pids) < 1500:
        r = cli.post("/v3/product/list", json={"filter":{"visibility":"ALL"},"limit":100,"last_id":last}).json()
        res = r.get("result",{})
        pids += [x["product_id"] for x in res.get("items",[])]
        last = res.get("last_id","")
        if not last: break
    brooch = []
    for j in range(0,len(pids),100):
        r = cli.post("/v4/product/info/attributes",
                     json={"filter":{"product_id":pids[j:j+100],"visibility":"ALL"},"limit":1000}).json()
        for it in r.get("result",[]):
            if str(it.get("type_id"))=="87458886" and it.get("offer_id") not in DONE:
                brooch.append(it)
        if len(brooch) >= N: break
    brooch = brooch[:N]
    ids = [b["id"] for b in brooch]
    pr = cli.post("/v3/product/info/list", json={"product_id":ids,"sku":[],"offer_id":[]}).json()
    pmap = {it["id"]: it for it in pr.get("result",{}).get("items",[])}
    out=[]
    for it in brooch:
        am = amap(it.get("attributes",[]))
        pi = pmap.get(it["id"],{})
        prc = pi.get("price",{}) or {}
        out.append({
            "ozon_id": it.get("id"), "name": it.get("name"), "offer_id": it.get("offer_id"),
            "primary_image": it.get("primary_image"), "images": it.get("images",[]),
            "price": prc.get("price"), "currency": prc.get("currency_code"),
            "old_price": prc.get("old_price"),
            "description_html": am.get("4191",""),
        })
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("saved", len(out), "| sample price:", out[0]["price"], out[0]["currency"] if out else "-")
