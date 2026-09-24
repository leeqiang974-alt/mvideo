# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import httpx
CRED=Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
L=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=L.index("2536021"); key=L[i+1]
h={"Client-Id":"2536021","Api-Key":key,"Content-Type":"application/json"}
CAT="29183107"
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=40) as c:
    pids,last=[],''
    for _ in range(30):
        r=c.post("/v3/product/list",json={"filter":{"visibility":"ALL"},"limit":1000,"last_id":last}).json()
        res=r.get("result",{}); pids+=[x["product_id"] for x in res.get("items",[])]; last=res.get("last_id","")
        if not last: break
    out=[]
    for j in range(0,len(pids),900):
        r=c.post("/v4/product/info/attributes",json={"filter":{"product_id":pids[j:j+900],"visibility":"ALL"},"limit":1000}).json()
        for it in r.get("result",[]):
            if str(it.get("description_category_id"))==CAT and len(out)<15:
                out.append({"offer_id":it["offer_id"],"ozon_id":it["id"],"name":it.get("name","")[:100],
                            "imgs":it.get("images",[])[:3]})
    # prices
    ids=[o["ozon_id"] for o in out]
    if ids:
        r=c.post("/v3/product/info/list",json={"product_id":ids,"sku":[],"offer_id":[]}).json()
        pm={it["id"]:it.get("price") for it in r.get("items",[])}
        for o in out: o["price_cny"]=pm.get(o["ozon_id"])
    Path(r"C:\MvideoERP\work\scrunchie_input.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
    print("pulled",len(out))
    for o in out: print(" ",o["offer_id"],o["price_cny"],(o["name"] or "")[:40])
