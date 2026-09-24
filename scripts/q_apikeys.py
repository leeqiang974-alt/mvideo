# -*- coding: utf-8 -*-
"""List ERP_API_DIR contents and read ERP_API_DIR value from .env."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENV = r"C:\OzonERP\.env"
for line in open(ENV, encoding="utf-8", errors="replace"):
    line = line.strip()
    if line.startswith("ERP_API_DIR"):
        v = line.split("=", 1)[1].strip()
        print("ERP_API_DIR =", v)
        d = os.path.expanduser(v)
        if os.path.isdir(d):
            for f in os.listdir(d):
                print("  -", f)
        else:
            print("  (dir not found)")
        break
