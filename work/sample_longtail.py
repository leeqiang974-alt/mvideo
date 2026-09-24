# -*- coding: utf-8 -*-
"""Sample 2 products per target long-tail category to identify them."""
import json
from pathlib import Path
import httpx
CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
items=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=items.index("3815760"); key=items[i+1]
h={"Client-Id":"3815760","Api-Key":key,"Content-Type":"application/json"}
targets=["17028959","17028743","41777465","29183107","17028653","17028964","200001479","17028749"]
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=40) as c:
    pids,last=[],''
    while len(pids)<1200:
        r=c.post("/v3/product/list",json={"filter":{"visibility":"ALL"},"limit":100,"last_id":last}).json()
        res=r.get("result",{}); pids+=[x["product_id"] for x in res.get("items",[])]; last=res.get("last_id","")
        if not last: break
    seen={}
    for j in range(0,len(pids),100):
        r=c.post("/v4/product/info/attributes",json={"filter":{"product_id":pids[j:j+100],"visibility":"ALL"},"limit":1000}).json()
        for it in r.get("result",[]):
            cid=str(it.get("description_category_id"))
            if cid in targets and cid not in seen:
                seen[cid]={"type_id":it.get("type_id"),"names":[]}
            if cid in seen and len(seen[cid]["names"])<2:
                seen[cid]["names"].append(it.get("name","")[:70])
    Path(r"C:\MvideoERP\work\longtail_samples.json").write_text(json.dumps(seen,ensure_ascii=False,indent=2),encoding="utf-8")
    for t in targets:
        print(t, "->", seen.get(t))
