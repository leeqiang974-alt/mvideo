# -*- coding: utf-8 -*-
"""Aggregate unique Ozon categories + product counts across all 5 stores."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import json, time
from collections import defaultdict
from pathlib import Path
import httpx

CRED=Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
lines=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
import re
def key_after(cid):
    for i,x in enumerate(lines):
        if cid in x:
            for j in range(i+1,min(i+4,len(lines))):
                m=re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",lines[j])
                if m: return m.group(0)
    raise ValueError(cid)
STORES={"kc":"2367028","xymall":"2536021","xymall2":"3770019","xymallc":"3815760","xymallD":"5736838"}

cat=defaultdict(lambda:{"count":0,"stores":set(),"name":""})
for name,cid in STORES.items():
    key=key_after(cid)
    h={"Client-Id":cid,"Api-Key":key,"Content-Type":"application/json"}
    try:
        with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=40) as c:
            pids,last=[],''
            for _ in range(60):
                r=c.post("/v3/product/list",json={"filter":{"visibility":"ALL"},"limit":1000,"last_id":last}).json()
                res=r.get("result",{})
                pids+=[x["product_id"] for x in res.get("items",[])]
                last=res.get("last_id","")
                if not last: break
            # attributes in chunks of 1000
            for j in range(0,len(pids),900):
                r=c.post("/v4/product/info/attributes",json={"filter":{"product_id":pids[j:j+900],"visibility":"ALL"},"limit":1000}).json()
                for it in r.get("result",[]):
                    cid2=str(it.get("description_category_id"))
                    cat[cid2]["count"]+=1
                    cat[cid2]["stores"].add(name)
                    cat[cid2]["name"]=it.get("name","")[:0] or cat[cid2]["name"]
            print(name, "products:", len(pids))
    except Exception as e:
        print(name,"ERR",repr(e)[:120])
out=[]
for cid,v in cat.items():
    out.append({"ozon_category_id":cid,"count":v["count"],"stores":",".join(sorted(v["stores"]))})
out.sort(key=lambda x:-x["count"])
Path(r"C:\MvideoERP\work\category_inventory.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
print("TOTAL unique categories:",len(out))
print("total SKU rows:",sum(x["count"] for x in out))
for x in out[:25]: print(f"  {x['ozon_category_id']:>12}  {x['count']:>5}  {x['stores']}")
