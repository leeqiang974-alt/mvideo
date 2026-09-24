# -*- coding: utf-8 -*-
import sys, re, json
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from sqlalchemy import create_engine, text
import httpx
# DB
db_url=None
for line in Path(r"C:\OzonERP\.env").read_text(encoding="utf-8",errors="ignore").splitlines():
    if line.startswith("DATABASE_URL="): db_url=line.split("=",1)[1].strip()
eng=create_engine(db_url)
# kc store products per category (just category ids)
L=[x.strip() for x in Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt").read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
def key_for(cid):
    for i,x in enumerate(L):
        if cid in x:
            for j in range(i+1,min(i+4,len(L))):
                m=re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",L[j])
                if m: return m.group(0)
kc_key=key_for("2367028")
h={"Client-Id":"2367028","Api-Key":kc_key,"Content-Type":"application/json"}
kc_counts={}
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=40) as c:
    pids,last=[],''
    for _ in range(60):
        r=c.post("/v3/product/list",json={"filter":{"visibility":"ALL"},"limit":1000,"last_id":last}).json()
        res=r.get("result",{}); pids+=[x["product_id"] for x in res.get("items",[])]; last=res.get("last_id","")
        if not last: break
    print("kc products:",len(pids))
    for j in range(0,len(pids),900):
        r=c.post("/v4/product/info/attributes",json={"filter":{"product_id":pids[j:j+900],"visibility":"ALL"},"limit":1000}).json()
        for it in r.get("result",[]):
            cid=str(it.get("description_category_id")); kc_counts[cid]=kc_counts.get(cid,0)+1
# merge with existing inventory
inv=json.load(open(r"C:\MvideoERP\work\category_inventory.json",encoding="utf-8"))
total=0
rows=[]
for x in inv:
    cid=x["ozon_category_id"]
    cnt=x["count"]+kc_counts.get(cid,0)
    total+=cnt
    rows.append({"cid":cid,"count":cnt})
for cid,cnt in kc_counts.items():
    if cid not in {r["cid"] for r in rows}:
        rows.append({"cid":cid,"count":cnt}); total+=cnt
rows.sort(key=lambda r:-r["count"])
# get Chinese names from global cache
ids=[r["cid"] for r in rows]
names={}
with eng.connect() as conn:
    for k in range(0,len(ids),500):
        q="SELECT category_id,title,title_zh FROM ozon_global_category_cache WHERE category_id = ANY(CAST(:ids AS text[]))"
        res=conn.execute(text(q),{"ids":[int(i) for i in ids[k:k+500]]}).fetchall()
        for cid,title,tzh in res: names[str(cid)]={"title":title,"zh":tzh}
out=[]
for r in rows:
    n=names.get(r["cid"],{})
    out.append({"ozon_category_id":r["cid"],"count":r["count"],"ru":(n.get("title") or "")[:60],"zh":(n.get("zh") or "")[:60]})
Path(r"C:\MvideoERP\work\category_inventory_full.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
print("TOTAL rows:",len(out),"SKU:",total)
for r in out[:30]: print(f'  {r["ozon_category_id"]:>12}  {r["count"]:>5}  {r["zh"] or r["ru"]}')
