# -*- coding: utf-8 -*-
import sqlite3
import json

con = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = con.cursor()
cur.execute(
    "SELECT id, name, attributes_json FROM migration_items "
    "WHERE offer_id=? AND batch_id=(SELECT MAX(batch_id) FROM migration_items WHERE offer_id=?)",
    ("sellersku0002", "sellersku0002"),
)
r = cur.fetchone()
print("id:", r[0])
print("name:", r[1])
attrs = json.loads(r[2])
print("=== 描述相关属性 (4191/85/4389/6548) ===")
for a in attrs:
    aid = a.get("id")
    if aid in (4191, 85, 4389, 6548):
        vals = a.get("values", [])
        v = vals[0].get("value", "") if vals else ""
        print(f"attr {aid}: {v[:150]}")
# list all attr ids to see what's available
print("=== 全部属性 id ===")
print([a.get("id") for a in attrs])
con.close()
