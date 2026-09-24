# -*- coding: utf-8 -*-
"""更新最新切带机迁移项：product_id / 真实类目 / 状态。"""
import sqlite3

conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute(
    "UPDATE migration_items SET mv_product_id=?, mv_group_id=?, mv_infomodel_id=?, status=?, upload_ref=? WHERE id=?",
    (
        "403160022",
        "604171101",
        "INF-307590",
        "submitted",
        "out_dispenser_sellersku0002.xlsx",
        14,
    ),
)
conn.commit()
cur.execute("SELECT id, offer_id, mv_product_id, mv_group_id, mv_infomodel_id, status, upload_ref FROM migration_items WHERE id=14")
print("UPDATED:", cur.fetchone())
conn.close()
