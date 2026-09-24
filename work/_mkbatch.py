# -*- coding: utf-8 -*-
import sys, json, glob
from pathlib import Path
import httpx
sys.stdout.reconfigure(encoding="utf-8")
WORK=Path(r"E:\mvideo\MvideoERP\work")
H={"api-key":"e250064c-af03-48f0-8f11-4eccb97f6aa8","Content-Type":"application/json"}
allp={}
for f in glob.glob(str(WORK/"auto_*.json")):
    try: data=json.load(open(f,encoding="utf-8"))
    except: continue
    for o in data:
        of=o.get("offer_id")
        if of and of not in allp: allp[of]=o
offers=list(allp.keys())
built=set()
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers=H,timeout=120) as c:
    for i in range(0,len(offers),1000):
        chunk=offers[i:i+1000]; cursor=None
        while True:
            body={"filter":{"offer_id":chunk},"limit":1000}
            if cursor: body["cursor"]=cursor
            j=c.post("/v1/product/mapping/list",json=body).json()
            for m in j.get("mappings",[]):
                if not m.get("is_archived"): built.add(m["offer_id"])
            cursor=j.get("next_cursor")
            if not cursor: break
tested={"OZBE822BF07A","OZ476C07C52E","OZ719D0F170F","OZAAC71B8DE2"}
sel=[]
for of,o in allp.items():
    if of in built or of in tested: continue
    pi=o.get("primary_image"); imgs=o.get("images",[])
    if not pi or not imgs: continue
    if "alicdn.com" in pi and "ozonstatic" not in pi: continue  # skip 1688 hotlink
    if not o.get("description_html"): continue
    if not o.get("price"): continue
    sel.append(o)
    if len(sel)>=30: break
(WORK/"_batch30.json").write_text(json.dumps(sel,ensure_ascii=False),encoding="utf-8")
print("built:",len(built),"selected for batch test:",len(sel))
from collections import Counter
print(Counter(("oss" if "aliyuncs" in o["primary_image"] else "cn") for o in sel))
