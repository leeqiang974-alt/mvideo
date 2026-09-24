# -*- coding: utf-8 -*-
"""查 Ozon ERP Postgres 中的分类缓存（只读，不输出任何密钥）"""
import os
import json

# 读取 .env 的 DATABASE_URL（仅脚本内部使用）
db_url = None
env_path = r"C:\OzonERP\.env"
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                db_url = line.split("=", 1)[1].strip()
                break

print("DB_KIND:", ("postgres" if db_url and db_url.startswith("postgres") else "sqlite" if db_url else "NOT_FOUND"))

if not db_url:
    print("NO_DB_URL")
    raise SystemExit(0)

# 用 SQLAlchemy（Ozon ERP venv 已装）
from sqlalchemy import create_engine, text
engine = create_engine(db_url, pool_pre_ping=False)

with engine.connect() as conn:
    # 1. 分类相关表
    tables = conn.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%categor%' OR table_name LIKE '%cat%'"
    )).fetchall()
    print("CAT_TABLES:", json.dumps([t[0] for t in tables], ensure_ascii=False))

    # 2. 每张表：行数 + 列 + 抽样（中文标题）
    for (tname,) in tables:
        try:
            cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{tname}"')).scalar()
            cols = [r[0] for r in conn.execute(text(
                f"SELECT column_name FROM information_schema.columns WHERE table_name='{tname}'"
            )).fetchall()]
            print(f"=== {tname} rows={cnt} ===")
            print("COLS:", json.dumps(cols, ensure_ascii=False))
            if cnt and cnt > 0:
                rows = conn.execute(text(f'SELECT * FROM "{tname}" LIMIT 3')).fetchall()
                for r in rows:
                    d = {k: (str(v)[:80] if v is not None else None) for k, v in zip(cols, r)}
                    print("SAMPLE:", json.dumps(d, ensure_ascii=False))
        except Exception as e:
            print(f"ERR {tname}: {e}")

engine.dispose()
