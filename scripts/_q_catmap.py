# -*- coding: utf-8 -*-
"""更新 category_mappings 表：切带机 17029021 -> GROUP-604171101 / INF-307590。"""
import sqlite3

conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(category_mappings)")
cols = [r[1] for r in cur.fetchall()]
print("COLS:", cols)
cur.execute("SELECT * FROM category_mappings WHERE ozon_category_id IN ('17029021','17029021') OR mv_group_id IN ('604171101','605085601')")
rows = cur.fetchall()
for r in rows:
    print("ROW:", r)
conn.close()
