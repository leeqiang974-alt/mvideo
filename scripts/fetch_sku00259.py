# -*- coding: utf-8 -*-
"""Fetch full Ozon data for SKU00259 family (shop_id=1 Ксималл) and dump JSON."""
import sys, json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\OzonERP")
from backend.app.database import SessionLocal
from backend.app.sync_service import _credentials
from backend.app.integrations.ozon_seller import OzonSellerClient
from sqlalchemy import text

s = SessionLocal()
rows = s.execute(text("SELECT id, ozon_product_id, offer_id, name FROM products WHERE offer_id LIKE 'SKU00259%' OR offer_id = 'SKU00259' ORDER BY id")).fetchall()
product_ids = [int(r[1]) for r in rows]
print("SKU00259 family:", len(rows), "products")
for r in rows:
    print(" ", r[2], "->", r[1])

client_id, api_key = _credentials(s, 1)
print("credentials resolved OK (hidden)")
s.close()

out = {}
with OzonSellerClient(client_id=client_id, api_key=api_key) as client:
    # 1) product info
    info = client.get_product_info(product_ids=product_ids)
    out["product_info"] = info
    print("product_info keys:", list(info.keys()) if isinstance(info, dict) else type(info))

    # 2) pictures
    try:
        pics = client.get_product_pictures(product_ids=product_ids)
        out["pictures"] = pics
        print("pictures keys:", list(pics.keys()) if isinstance(pics, dict) else type(pics))
    except Exception as e:
        out["pictures_err"] = str(e)
        print("pictures ERR:", e)

    # 3) attributes v4
    try:
        attrs = client.get_product_attributes_v4(product_ids=product_ids)
        out["attributes"] = attrs
        print("attributes keys:", list(attrs.keys()) if isinstance(attrs, dict) else type(attrs))
    except Exception as e:
        out["attributes_err"] = str(e)
        print("attributes ERR:", e)

    # 4) related skus
    try:
        rel = client.get_related_skus(skus=[int(r[4] if len(r)>4 else 0) for r in []])
    except Exception:
        pass
    # skus from product_info items
    try:
        items = info.get("result", {}).get("items", []) if isinstance(info, dict) else []
        sku_list = [it.get("sku") for it in items if isinstance(it, dict) and it.get("sku")]
        if sku_list:
            rel = client.get_related_skus(skus=sku_list)
            out["related_skus"] = rel
            print("related_skus:", json.dumps(rel, ensure_ascii=False)[:500])
    except Exception as e:
        out["related_skus_err"] = str(e)
        print("related_skus ERR:", e)

    # 5) warehouses (for stock)
    try:
        wh = client.list_warehouses()
        out["warehouses"] = wh
        print("warehouses OK:", json.dumps(wh, ensure_ascii=False)[:400])
    except Exception as e:
        out["warehouses_err"] = str(e)
        print("warehouses ERR:", e)

# save JSON locally on the notebook for easy copy
with open(r"C:\OzonERP\sku00259_full.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\nSAVED C:\\OzonERP\\sku00259_full.json")
print("SIZE:", len(json.dumps(out, ensure_ascii=False)))
