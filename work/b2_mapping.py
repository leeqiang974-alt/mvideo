# -*- coding: utf-8 -*-
import json
from pathlib import Path
import httpx
offers=["SKU00166-NR6353","SKU00168-NR12001","SKU00168-NR90367","SKU00169-XZ3523-2","SKU00169-XZ3523-3","SKU00170-NR90149","SKU00170-NR90150","SKU00164-Курячая ножка5589","SKU00164-русалка5567","SKU00164-Череп6195","SKU00164-Нож6155","SKU00164-авокадо5565","SKU00164-Нож6159","SKU00164-Дом6370","SKU00164-помело6197","SKU00164-персик5573","SKU00164-Нож6098","SKU00164-циганотераптор6981","SKU00164-ананас5550","SKU00164-автомобиль7304"]
env={}
for line in Path(r"C:\MvideoERP\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); env[k.strip()]=v.strip()
key=env["OMNI_API_KEY"]
with httpx.Client(base_url="https://omni-net.sellers.mvideo.ru",headers={"api-key":key,"Content-Type":"application/json"},timeout=30) as c:
    r=c.post("/v1/product/mapping/list",json={"filter":{"offer_id":offers},"limit":100})
m=r.json().get("mappings",[])
print("HTTP",r.status_code,"mapped:",len(m))
json.dump(m,open(r"C:\MvideoERP\work\b2_mapping.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
got={x.get("offer_id") for x in m}
for x in m: print("  ",x.get("offer_id"),"->",x.get("product_id"))
print("NOT:",[o for o in offers if o not in got])
