# -*- coding: utf-8 -*-
"""Read DATABASE_URL (redacted) and query Postgres for SKU00259."""
import os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENV = r"C:\OzonERP\.env"
db_url = None
for line in open(ENV, encoding="utf-8", errors="replace"):
    line = line.strip()
    if line.upper().startswith("DATABASE_URL"):
        db_url = line.split("=", 1)[1].strip()
        break

print("=== DATABASE_URL (redacted) ===")
if db_url:
    v = re.sub(r"(:\/\/[^:]+:)([^@]+)(@)", r"\1***\3", db_url)
    print(v)
else:
    print("NOT FOUND")

# Try to connect via SQLAlchemy using the app's session factory
try:
    sys.path.insert(0, r"C:\OzonERP")
    from backend.app.database import SessionLocal
    from sqlalchemy import text

    s = SessionLocal()
    print("\n=== CONNECTED via app SessionLocal ===")
    # shops
    rows = s.execute(text("SELECT id, name, legal_entity, is_active FROM shops ORDER BY id")).fetchall()
    print("SHOPS:", [tuple(r) for r in rows])
    # search SKU00259 across relevant tables
    for tbl in ["skus", "source_variants", "listing_variants", "products"]:
        try:
            r = s.execute(text(f"SELECT * FROM {tbl} WHERE CAST(id AS TEXT) LIKE '%00259%' OR CAST(seller_sku AS TEXT) LIKE '%00259%' OR CAST(source_sku AS TEXT) LIKE '%00259%' OR CAST(offer_id AS TEXT) LIKE '%00259%' LIMIT 5")).fetchall()
            print(f"\n{tbl} rows matching 00259:", len(r))
            if r:
                for row in r[:3]:
                    print(" ", tuple(str(x)[:80] for x in row))
        except Exception as e:
            print(f"{tbl}: ERR {e}")
    s.close()
except Exception as e:
    print("CONNECT ERR:", e)
