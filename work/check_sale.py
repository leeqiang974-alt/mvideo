import sqlite3, json
from pathlib import Path
import httpx
env={}
for line in Path(r"C:\MvideoERP\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["OMNI_API_KEY"]
pids=[403161274,403161275,403161276,403161277,403161278]
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":key,"Content-Type":"application/json"},timeout=30) as c:
    st=c.post("/v1/product/stock/info",json={"filter":{"product_id":[str(p) for p in pids],"location_id":[10011496]},"limit":20}).json()
for x in st.get("stocks",[]): print(x)
