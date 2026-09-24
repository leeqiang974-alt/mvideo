# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute("SELECT id, offer_id, name, ozon_category_id, ozon_category_name, mv_group_id, mv_infomodel_id FROM migration_items WHERE offer_id IN ('sellersku0002','sellersku0001')")
for r in cur.fetchall():
    print(r)
conn.close()
