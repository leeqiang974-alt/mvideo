# -*- coding: utf-8 -*-
"""查 sellersku0002 切带机的完整属性（判断形态），并查 Ozon 商品名称。"""
import sqlite3, json
conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute("SELECT id, offer_id, name, attributes_json, images_json FROM migration_items WHERE offer_id='sellersku0002' ORDER BY id DESC LIMIT 1")
r = cur.fetchone()
if r:
    print("ID:", r[0], "OFFER:", r[1])
    print("NAME:", r[2])
    try:
        attrs = json.loads(r[3]) if r[3] else []
        print("ATTRS count:", len(attrs))
        for a in attrs[:60]:
            print("  ", a)
    except Exception as e:
        print("ATTRS ERR:", e, "RAW:", str(r[3])[:500])
    try:
        imgs = json.loads(r[4]) if r[4] else []
        print("IMGS count:", len(imgs))
    except Exception as e:
        print("IMGS ERR:", e)
conn.close()
