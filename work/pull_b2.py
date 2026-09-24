# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import httpx
CRED=Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
L=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=L.index("2536021"); key=L[i+1]
h={"Client-Id":"2536021","Api-Key":key,"Content-Type":"application/json"}
CATS={"brooch":"17027899","scrunchie":"29183107","carpet":"17028727","hat":"41777465","suitcase":"17027904","container":"17027907","kaleidoscope":"17028973"}
START=15; N=30
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=40) as c:
    pids,last=[],''
    for _ in range(30):
        r=c.post("/v3/product/list",json={"filter":{"visibility":"ALL"},"limit":1000,"last_id":last}).json()
        res=r.get("result",{}); pids+=[x["product_id"] for x in res.get("items",[])]; last=res.get("last_id","")
        if not last: break
    buckets={k:[] for k in CATS}
    seen={k:0 for k in CATS}
    for j in range(0,len(pids),900):
        r=c.post("/v4/product/info/attributes",json={"filter":{"product_id":pids[j:j+900],"visibility":"ALL"},"limit":1000}).json()
        for it in r.get("result",[]):
            cid=str(it.get("description_category_id"))
            for k,want in CATS.items():
                if cid==want:
                    seen[k]+=1
                    if START<=seen[k]<START+N and len(buckets[k])<N:
                        buckets[k].append({"offer_id":it["offer_id"],"ozon_id":it["id"],"name":it.get("name","")[:100],"imgs":it.get("images",[])[:3]})
    for k,items in buckets.items():
        ids=[o["ozon_id"] for o in items]
        if ids:
            r=c.post("/v3/product/info/list",json={"product_id":ids,"sku":[],"offer_id":[]}).json()
            pm={it["id"]:it.get("price") for it in r.get("items",[])}
            for o in items: o["price_cny"]=pm.get(o["ozon_id"])
        Path(rf"C:\MvideoERP\work\{k}_b2input.json").write_text(json.dumps(items,ensure_ascii=False,indent=1),encoding="utf-8")
        print(k,len(items))
