# -*- coding: utf-8 -*-
import re, os, sqlite3, sys

# 1) parse ozonapi.txt -> list of (label, client_id) WITHOUT keys
path = r"C:\Users\Administrator\Desktop\api\ozonapi.txt"
lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
print("=== OZON API FILE (lines: %d) ===" % len(lines))
stores = []
cur_label = None
for ln in lines:
    s = ln.strip()
    if not s:
        continue
    # a label line: contains chinese/cyrillic/store name and no long digit key
    m_id = re.search(r"Client-Id\s*[:=]\s*(\d+)", s, re.I)
    m_key = re.search(r"Api-Key\s*[:=]\s*([A-Za-z0-9\-_]+)", s, re.I)
    if m_id:
        # try to find a nearby label on the same line
        label = s.split("Client-Id")[0].strip(" ::|-\t") or cur_label or "?"
        stores.append((label, m_id.group(1)))
    else:
        # treat non-empty non-key line as a label
        if not m_key and len(s) < 60 and not s.startswith(("#",";","//")):
            cur_label = s

print("Detected stores:")
for lab, cid in stores:
    print("  label=%-30s client_id=%s" % (lab, cid))

# 2) DB state
db = r"C:\MvideoERP\mvideo_erp.db"
if os.path.exists(db):
    con = sqlite3.connect(db)
    cur = con.cursor()
    def q(sql):
        try:
            cur.execute(sql); return cur.fetchall()
        except Exception as e:
            return [("ERR", str(e))]
    print("\n=== TABLES ===")
    for r in q("SELECT name FROM sqlite_master WHERE type='table'"):
        print("  ", r[0])
    print("\n=== category_mappings count ===")
    for r in q("SELECT status, COUNT(*) FROM category_mappings GROUP BY status"):
        print("  ", r)
    print("\n=== migration_items count by status ===")
    try:
        cols = [c[1] for c in q("PRAGMA table_info(migration_items)")]
        print("  cols:", cols)
    except Exception as e:
        print("  no migration_items", e)
    con.close()
else:
    print("DB NOT FOUND at", db)
