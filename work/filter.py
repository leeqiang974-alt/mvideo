import json, sys
sys.stdout.reconfigure(encoding="utf-8")
for f in ["scrunchie_input","hat_input"]:
    p=rf"E:\mvideo\MvideoERP\work\{f}.json"
    d=json.load(open(p,encoding="utf-8"))
    good=[x for x in d if x.get("imgs") and len(x["imgs"])>0]
    json.dump(good,open(p.replace(".json","_clean.json"),"w",encoding="utf-8"),ensure_ascii=False)
    print(f,len(d),"->",len(good))
