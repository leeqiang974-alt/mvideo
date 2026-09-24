import sqlite3, json
from pathlib import Path
import httpx
env={}
for line in Path(r"C:\MvideoERP\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["OMNI_API_KEY"]
# get all offers from input files
import glob
offers=[]
for f in glob.glob(r"C:\MvideoERP\work\*_input.json")+glob.glob(r"C:\MvideoERP\work\*_b2input.json"):
    for p in json.load(open(f,encoding="utf-8")):
        offers.append(p["offer_id"])
print("total offers",len(offers))
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":key,"Content-Type":"application/json"},timeout=30) as c:
    r=c.post("/v1/product/mapping/list",json={"filter":{"offer_id":offers},"limit":500})
m=r.json().get("mappings",[])
print("mapped now",len(m))
