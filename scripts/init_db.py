"""Create all M.Video ERP tables and print the table list.

Run with the project venv:
    .venv\\Scripts\\python.exe scripts\\init_db.py
Idempotent (CREATE TABLE IF NOT EXISTS).
"""

import os
import sys

# make ``app.*`` importable: <project>/backend on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.database import Base, engine, init_db  # noqa: E402


def main() -> int:
    init_db()
    tables = sorted(Base.metadata.tables.keys())
    print("init_db: OK")
    print(f"engine: {engine.url}")
    print(f"tables ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
