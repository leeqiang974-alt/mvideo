# -*- coding: utf-8 -*-
import sys, urllib.request, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    r = urllib.request.urlopen("http://127.0.0.1:8077/health", timeout=10)
    print("HTTP", r.status)
    print(r.read().decode("utf-8")[:400])
except Exception as e:
    print("ERR", repr(e))
