# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")))
from sqlalchemy import select
from app.database import SessionLocal, init_db
from app.models import MigrationBatch, MigrationItem

init_db()
s = SessionLocal()
batches = s.execute(select(MigrationBatch).order_by(MigrationBatch.id)).scalars().all()
for b in batches:
    print(f"batch_id={b.id} ref={b.batch_ref} status={b.status} created={b.created_at}")
print("----")
items = s.execute(
    select(MigrationItem)
    .where(MigrationItem.offer_id.like("%SKU00259%"))
    .order_by(MigrationItem.id)
).scalars().all()
print(f"SKU00259 items: {len(items)}")
for it in items:
    print(f"  id={it.id} batch={it.batch_id} offer={it.offer_id} status={it.status} mv_pid={it.mv_product_id} price_kop={it.price_kopecks} oldprice={it.old_price_kopecks} stock={it.stock_count}")
s.close()
