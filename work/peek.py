import json,sys
sys.stdout.reconfigure(encoding="utf-8")
d=json.load(open(r"E:\mvideo\MvideoERP\work\brooch_b2input.json",encoding="utf-8"))
print(list(d[0].keys()))
