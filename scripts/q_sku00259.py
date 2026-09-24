# -*- coding: utf-8 -*-
"""Dump SKU00259 full family from Ozon ERP Postgres (shop=Ксималл, id=1)."""
import sys, json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\OzonERP")
from backend.app.database import SessionLocal
from sqlalchemy import text

s = SessionLocal()

print("=== SKUS (full family) ===")
rows = s.execute(text("SELECT * FROM skus WHERE seller_sku LIKE 'SKU00259%' OR seller_sku = 'SKU00259' ORDER BY id")).fetchall()
print("count:", len(rows))
for r in rows:
    print(" | ".join(str(x)[:120] if x is not None else "NULL" for x in r))

print("\n=== PRODUCTS (full family) ===")
rows = s.execute(text("SELECT * FROM products WHERE offer_id LIKE 'SKU00259%' OR offer_id = 'SKU00259' ORDER BY id")).fetchall()
print("count:", len(rows))
for r in rows:
    print(" | ".join(str(x)[:120] if x is not None else "NULL" for x in r))

print("\n=== PRODUCT raw_payload detail (first 2) ===")
rows = s.execute(text("SELECT offer_id, raw_payload FROM products WHERE offer_id LIKE 'SKU00259%' ORDER BY id LIMIT 2")).fetchall()
for offer_id, payload in rows:
    print(f"\n--- {offer_id} ---")
    try:
        d = json.loads(payload)
        print(json.dumps(d, ensure_ascii=False, indent=1)[:3000])
    except Exception as e:
        print("PARSE ERR", e, str(payload)[:800])

s.close()
