# -*- coding: utf-8 -*-
"""查询 Ozon ERP 分类缓存表结构与数据量（只读）"""
import sqlite3
import json

conn = sqlite3.connect(r"C:/OzonERP/ozon_erp.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 1. 找分类相关表
tables = c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%categor%' OR name LIKE '%cat%' OR name LIKE '%category%')"
).fetchall()
print("CAT_TABLES:", json.dumps([t[0] for t in tables], ensure_ascii=False))

# 2. 每个分类表：列结构 + 行数 + 抽样
for t in tables:
    name = t[0]
    try:
        cols = c.execute(f"PRAGMA table_info('{name}')").fetchall()
        cnt = c.execute(f"SELECT COUNT(*) FROM '{name}'").fetchone()[0]
        print(f"\n=== {name} (rows={cnt}) ===")
        print("COLS:", json.dumps([col[1] for col in cols], ensure_ascii=False))
        if cnt > 0:
            sample = c.execute(f"SELECT * FROM '{name}' LIMIT 3").fetchall()
            for row in sample:
                d = {k: (str(v)[:60] if v is not None else None) for k, v in dict(row).items()}
                print("SAMPLE:", json.dumps(d, ensure_ascii=False))
    except Exception as e:
        print(f"ERR {name}: {e}")

conn.close()
