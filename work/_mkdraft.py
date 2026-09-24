# -*- coding: utf-8 -*-
import sys, json, glob
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
WORK=Path(r"E:\mvideo\MvideoERP\work")
target="OZAAC71B8DE2"
found=None
for f in glob.glob(str(WORK/"auto_*.json")):
    try: data=json.load(open(f,encoding="utf-8"))
    except: continue
    for o in data:
        if o.get("offer_id")==target:
            found=o; print("found in",Path(f).name,"| imgs",len(o.get("images",[]))+1,"| price",o.get("price")); break
    if found: break
if found:
    (WORK/"_draft_test.json").write_text(json.dumps([found],ensure_ascii=False),encoding="utf-8")
    print("saved _draft_test.json")
else:
    print("NOT FOUND")
