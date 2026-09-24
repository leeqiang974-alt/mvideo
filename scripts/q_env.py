# -*- coding: utf-8 -*-
"""Read .env key names (no values) and query Postgres for SKU00259 / shop 'kc'."""
import os, re, sys

ENV = r"C:\OzonERP\.env"
print("=== .env KEYS ===")
if os.path.exists(ENV):
    for line in open(ENV, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k = line.split("=", 1)[0].strip()
        print(k)
else:
    print("NO ENV")

print("\n=== DATABASE URL VALUE (redacted) ===")
if os.path.exists(ENV):
    for line in open(ENV, encoding="utf-8", errors="replace"):
        if line.strip().upper().startswith("DATABASE_URL") or "postgres" in line.lower():
            v = line.strip()
            # redact password if present
            v = re.sub(r"(:\/\/[^:]+:)([^@]+)(@)", r"\1***\3", v)
            print(v)
