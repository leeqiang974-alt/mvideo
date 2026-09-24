# -*- coding: utf-8 -*-
import sys, json, glob
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import httpx
prods={}
for f in glob.glob(r"C:\MvideoERP\work\*_input.json")+glob.glob(r"C:\MvideoERP\work\*_b2input.json"):
    for p in json.load(open(f,encoding="utf-8")): prods[p["offer_id"]]=p
env={}
for line in Path(r"C:\MvideoERP\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip()
omni=env["OMNI_API_KEY"]
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":omni,"Content-Type":"application/json"},timeout=30) as c:
    r=c.post("/v1/product/mapping/list",json={"filter":{"offer_id":list(prods)},"limit":500})
    print(r.status_code)
    print(json.dumps(r.json(),ensure_ascii=False,indent=1)[:2000])
