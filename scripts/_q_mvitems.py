# -*- coding: utf-8 -*-
"""把切带机新 product_id (403160022) 写回 migration_items，标记新卡。"""
import sqlite3

conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute("SELECT id, offer_id, mv_product_id, status, mv_group_id FROM migration_items WHERE offer_id='sellersku0002' ORDER BY id DESC")
rows = cur.fetchall()
print("rows:", len(rows))
for r in rows:
    print("  ", r)
conn.close()
