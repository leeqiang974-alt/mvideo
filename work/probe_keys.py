# -*- coding: utf-8 -*-
import re
path = r"C:\Users\Administrator\Desktop\api\ozonapi.txt"
lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
for i, ln in enumerate(lines):
    s = ln.rstrip()
    if not s.strip():
        print("[%02d] <blank>" % i); continue
    # mask any long token that looks like a key
    masked = re.sub(r"[A-Za-z0-9_\-]{16,}", lambda m: m.group(0)[:4] + "***MASKED***", s)
    print("[%02d] %s" % (i, masked))
