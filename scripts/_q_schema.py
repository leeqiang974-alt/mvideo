# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect(r"E:\mvideo\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", [r[0] for r in cur.fetchall()])
for t in ["migration_batches", "migration_items"]:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [(r[1], r[2]) for r in cur.fetchall()]
        print(f"\n{t}:")
        for c in cols: print("  ", c)
    except Exception as e:
        print(t, "ERR", e)
conn.close()
