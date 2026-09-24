# -*- coding: utf-8 -*-
import sys, json, glob, os
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import httpx, time
DONE=r"C:\MvideoERP\work\pushed_done.json"
done=set(json.load(open(DONE,encoding="utf-8"))) if os.path.exists(DONE) else set()
prods={}
for f in glob.glob(r"C:\MvideoERP\work\*_input.json")+glob.glob(r"C:\MvideoERP\work\*_b2input.json"):
    for p in json.load(open(f,encoding="utf-8")): prods[p["offer_id"]]=p
env={}
for line in Path(r"C:\MvideoERP\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip()
omni=env["OMNI_API_KEY"]
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":omni,"Content-Type":"application/json"},timeout=30) as c:
    m=c.post("/v1/product/mapping/list",json={"filter":{"offer_id":list(prods)},"limit":500}).json().get("mappings",[])
oid2pid={x["offer_id"]:x["product_id"] for x in m}
ids=[prods[o]["ozon_id"] for o in oid2pid]
CRED=Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
L=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=L.index("2536021"); oz=L[i+1]
ph={"Client-Id":"2536021","Api-Key":oz,"Content-Type":"application/json"}
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=ph,timeout=40) as c:
    r=c.post("/v3/product/info/list",json={"product_id":ids,"sku":[],"offer_id":[]}).json()
    pm={it["id"]:float(it.get("price") or 0) for it in r.get("items",[])}
todo=[o for o in oid2pid if oid2pid[o] not in done]
print("todo",len(todo),"done",len(done))
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":omni,"Content-Type":"application/json"},timeout=30) as c:
    for o in todo:
        pid=oid2pid[o]; cny=pm.get(prods[o]["ozon_id"],0)
        rub=int(round(cny*12*1.1)); old=int(rub*2)
        pr=c.post("/v1/product/price/update",json={"items":[{"product_id":pid,"price":rub*100,"old_price":old*100,"offer_id":o}],"currency":"RUB"})
        sr=c.post("/v1/product/stock/update",json={"items":[{"product_id":pid,"count":999,"location_id":10011496}]})
        if pr.status_code==200 and not pr.json().get("failed") and sr.status_code==200 and not sr.json().get("failed"):
            done.add(pid); print("OK",pid)
        else:
            print("SKIP",pid,pr.status_code,sr.status_code); done.add(pid)
        time.sleep(0.5)
json.dump(list(done),open(DONE,"w",encoding="utf-8"))
print("saved done",len(done))
