# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
DONE=r"C:\MvideoERP\work\pushed_done.json"
d=set(json.load(open(DONE,encoding="utf-8")))
# remove None
d.discard(None)
json.dump(list(d),open(DONE,"w",encoding="utf-8"))
print(len(d))
