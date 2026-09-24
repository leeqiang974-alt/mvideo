# -*- coding: utf-8 -*-
import json
from pathlib import Path
import httpx
offers=["SKU00166-NR6353","SKU00168-NR12001","SKU00168-NR90367","SKU00169-XZ3523-2","SKU00169-XZ3523-3","SKU00170-NR90149","SKU00170-NR90150","SKU00164-Курячая ножка5589","SKU00164-русалка5567","SKU00164-Череп6195","SKU00164-Нож6155","SKU00164-авокадо5565","SKU00164-Нож6159","SKU00164-Дом6370","SKU00164-помело6197","SKU00164-персик5573","SKU00164-Нож6098","SKU00164-циганотераптор6981","SKU00164-ананас5550","SKU00164-автомобиль7304"]
m=json.load(open(r"C:\MvideoERP\work\b2_mapping.json",encoding="utf-8"))
oid2pid={x["offer_id"]:x["product_id"] for x in m}
env={}
for line in Path(r"C:\MvideoERP\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip()
omni_key=env["OMNI_API_KEY"]
CRED=Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
L=[x.strip() for x in CRED.read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
i=L.index("2536021"); oz_key=L[i+1]
h={"Client-Id":"2536021","Api-Key":oz_key,"Content-Type":"application/json"}
# Ozon prices by offer
with httpx.Client(base_url="https://api-seller.ozon.ru",headers=h,timeout=40) as oz:
    r=oz.post("/v3/product/info/list",json={"offer_id":offers,"product_id":[],"sku":[]})
    price_by_offer={it["offer_id"]:float(it.get("price") or 0) for it in r.json().get("items",[])}
print("ozon prices got:",len(price_by_offer))
price_items,stock_items=[],[]
for o in offers:
    pid=oid2pid.get(o)
    cny=price_by_offer.get(o,0)
    rub=int(round(cny*12*1.1)); old=int(round(rub*2))
    price_items.append({"product_id":pid,"price":rub*100,"old_price":old*100,"offer_id":o})
    stock_items.append({"product_id":pid,"count":999,"location_id":10011496})
print("sample prices:",set(p["price"] for p in price_items))
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":omni_key,"Content-Type":"application/json"},timeout=30) as om:
    pr=om.post("/v1/product/price/update",json={"items":price_items,"currency":"RUB"})
    print("price HTTP",pr.status_code)
    for f in pr.json().get("failed",[])[:5]: print("  PF:",f)
    sr=om.post("/v1/product/stock/update",json={"items":stock_items})
    print("stock HTTP",sr.status_code)
    for f in sr.json().get("failed",[])[:5]: print("  SF:",f)
