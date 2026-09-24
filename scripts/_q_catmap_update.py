# -*- coding: utf-8 -*-
"""更新切带机类目映射为真实值（GROUP-604171101 / INF-307590）。"""
import sqlite3

conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute(
    "UPDATE category_mappings SET mv_group_id=?, mv_group_name=?, mv_infomodel_id=?, status=? WHERE id=?",
    (
        "604171101",
        "Строительство и ремонт > Монтажный ручной инструмент > Диспенсер для монтажной ленты",
        "INF-307590",
        "confirmed",
        1,
    ),
)
conn.commit()
cur.execute("SELECT * FROM category_mappings WHERE id=1")
print("UPDATED:", cur.fetchone())
conn.close()
