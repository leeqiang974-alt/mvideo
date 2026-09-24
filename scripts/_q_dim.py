# -*- coding: utf-8 -*-
import sqlite3
import json

DB = r"C:\MvideoERP\mvideo_erp.db"

con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute(
    "SELECT id, offer_id, name, attributes_json FROM migration_items WHERE offer_id LIKE ?",
    ("%sellersku0002%",),
)
rows = cur.fetchall()
print("rows:", len(rows))
for r in rows:
    print("id:", r[0], "| offer:", r[1], "| name:", r[2])
    try:
        attrs = json.loads(r[3])
    except Exception as e:
        print("  attrs parse err:", e)
        continue
    s = json.dumps(attrs, ensure_ascii=False).lower()
    for kw in ["dlin", "shirin", "vysot", "dlina", "weight", "ves", "width", "length", "height", "gab", "razmer", "size"]:
        i = s.find(kw)
        if i >= 0:
            print(f"  KW '{kw}' found at {i}")
    if isinstance(attrs, dict):
        items = list(attrs.items())[:15]
        for k, v in items:
            print("  attr:", k, "=", str(v)[:90])
    elif isinstance(attrs, list):
        for a in attrs[:12]:
            print("  attr:", str(a)[:110])
con.close()
