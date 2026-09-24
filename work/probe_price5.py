import json
from pathlib import Path
import httpx
CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
items=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=items.index("2536021"); key=items[i+1]
h={"Client-Id":"2536021","Api-Key":key,"Content-Type":"application/json"}
ids=[2842763591,2842836715]
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=30) as c:
    for body in [
        {"filter":{"product_id":ids,"visibility":"ALL"},"limit":100},
        {"filter":{"product_id":ids},"limit":100},
    ]:
        r=c.post("/v4/product/info/prices",json=body)
        print("v4 HTTP",r.status_code)
        d=r.json()
        its=d.get("result",{}).get("items",[]) or d.get("items",[])
        print("  n:",len(its))
        if its: print("  item0:",json.dumps(its[0],ensure_ascii=False)[:400])
