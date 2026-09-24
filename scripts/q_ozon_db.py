# -*- coding: utf-8 -*-
"""Query Ozon ERP SQLite: list tables, find SKU00259 across all tables."""
import sqlite3
import sys

DB = r"C:\OzonERP\ozon_erp.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== TABLES ===")
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    try:
        cnt = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    except Exception:
        cnt = "?"
    print(f"{t}: {cnt} rows")

print("\n=== COLUMNS ===")
for t in tables:
    cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
    print(f"{t}: {','.join(cols)}")

con.close()
