# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(migration_items)")
cols = [r[1] for r in cur.fetchall()]
print("ITEM COLS:", cols)
print("---- batches ----")
cur.execute("SELECT id, batch_ref, status, total_count, priced_count, stocked_count, created_at FROM migration_batches ORDER BY id")
for r in cur.fetchall():
    print(r)
print("---- SKU00259 items ----")
try:
    cur.execute("SELECT id, batch_id, offer_id, status, mv_product_id, price_rub, stock, price_set, stock_set, mv_sap_code, mv_warehouse_code FROM migration_items WHERE offer_id LIKE '%SKU00259%' OR offer_id LIKE 'sellersku%' ORDER BY id")
    for r in cur.fetchall():
        print(r)
except Exception as e:
    print("ERR", e)
conn.close()
