# -*- coding: utf-8 -*-
import sys, json, glob, re, shutil
from pathlib import Path
import httpx, openpyxl
sys.stdout.reconfigure(encoding="utf-8")
WORK=Path(r"E:\mvideo\MvideoERP\work")
H={"api-key":"e250064c-af03-48f0-8f11-4eccb97f6aa8","Content-Type":"application/json"}
# gather all offers from auto json
allp={}
for f in glob.glob(str(WORK/"auto_*.json")):
    try: data=json.load(open(f,encoding="utf-8"))
    except: continue
    for o in data:
        of=o.get("offer_id")
        if of and of not in allp: allp[of]=o
offers=list(allp.keys())
# full mapping -> built offers
built=set()
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers=H,timeout=120) as c:
    for i in range(0,len(offers),1000):
        chunk=offers[i:i+1000]; cursor=None
        while True:
            body={"filter":{"offer_id":chunk},"limit":1000}
            if cursor: body["cursor"]=cursor
            j=c.post("/v1/product/mapping/list",json=body).json()
            for m in j.get("mappings",[]): built.add(m["offer_id"])
            cursor=j.get("next_cursor")
            if not cursor: break
print("total offers:",len(offers)," built(mapped):",len(built))
# candidates: not built, .cn main image, has images, has description, has price
cands=[]
for of,o in allp.items():
    if of in built: continue
    pi=o.get("primary_image"); imgs=o.get("images",[])
    if not pi or "ozonstatic.cn" not in pi: continue
    if not imgs: continue
    if not o.get("description_html"): continue
    cands.append(o)
print("unbuilt .cn candidates:",len(cands))
sel=cands[:3]
for o in sel: print("  pick:",o["offer_id"],o.get("price"),str(o["name"])[:40])
# rewrite image host to ir.ozone.ru
def ru(u): return u.replace("ir-20.ozonstatic.cn","ir.ozone.ru")
for o in sel:
    o["primary_image"]=ru(o["primary_image"])
    o["images"]=[ru(u) for u in o.get("images",[])]
(WORK/"_test_ru.json").write_text(json.dumps(sel,ensure_ascii=False),encoding="utf-8")
print("saved _test_ru.json")
