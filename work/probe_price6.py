import json
from pathlib import Path
import httpx
CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
items=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=items.index("2536021"); key=items[i+1]
h={"Client-Id":"2536021","Api-Key":key,"Content-Type":"application/json"}
ids=[2842763591]
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=30) as c:
    r=c.post("/v3/product/info/list",json={"product_id":ids,"sku":[],"offer_id":[]})
    it=r.json()["items"][0]
    for k,v in it.items():
        if "price" in k.lower() or "price" in json.dumps(v).lower():
            print(k,"=",json.dumps(v,ensure_ascii=False)[:200])
    print("ALL KEYS:", sorted(it.keys()))
