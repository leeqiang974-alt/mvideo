import json
from pathlib import Path
import httpx
CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
items=[x.strip() for x in raw if x.strip()]
i=items.index("2536021"); key=items[i+1]
h={"Client-Id":"2536021","Api-Key":key,"Content-Type":"application/json"}
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=30) as cli:
    r=cli.post("/v3/product/list",json={"filter":{"visibility":"ALL"},"limit":3}).json()
    ids=[x["product_id"] for x in r["result"]["items"]]
    pr=cli.post("/v3/product/info/list",json={"product_id":ids,"sku":[],"offer_id":[]}).json()
    print("TOP KEYS:", list(pr.keys()))
    print(json.dumps(pr, ensure_ascii=False)[:600])
