# -*- coding: utf-8 -*-
"""Query Ozon ERP Postgres: shop details, SKU00259 search across tables."""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\OzonERP")
from backend.app.database import SessionLocal
from sqlalchemy import text

s = SessionLocal()

def cols(tbl):
    try:
        r = s.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{tbl}' ORDER BY ordinal_position")).fetchall()
        return [x[0] for x in r]
    except Exception as e:
        return [f"ERR:{e}"]

# shops full
print("=== SHOPS ===")
for row in s.execute(text("SELECT * FROM shops ORDER BY id")):
    print(tuple(str(x)[:60] if x is not None else None for x in row))

# find tables that contain '00259' in any text/id column (sample first 200 rows each)
print("\n=== SEARCH 00259 ACROSS TABLES ===")
tables = ["skus","source_products","source_variants","listing_variants","listing_drafts","products","pipeline_products"]
for tbl in tables:
    try:
        c = cols(tbl)
        if not c or "ERR" in str(c[0]):
            print(f"{tbl}: cols ERR {c}"); continue
        # pick candidate columns: id, seller_sku, offer_id, source_sku, source_product_id, title, name
        cand = [x for x in c if x in ("id","seller_sku","offer_id","source_sku","source_product_id","source_variant_id","product_id","title","name","sku","sku_id")]
        conds = " OR ".join([f"CAST(\"{x}\" AS TEXT) LIKE '%00259%'" for x in cand]) if cand else "1=0"
        sql = f"SELECT * FROM \"{tbl}\" WHERE {conds} LIMIT 5"
        rows = s.execute(text(sql)).fetchall()
        print(f"\n{tbl} MATCHES: {len(rows)}  (cols: {c})")
        for row in rows[:3]:
            print(" ", tuple(str(x)[:70] if x is not None else None for x in row))
    except Exception as e:
        s.rollback()
        print(f"{tbl}: ERR {e}")

s.close()
