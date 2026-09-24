import json
d=json.load(open(r"E:\mvideo\MvideoERP\work\hat_b2input.json",encoding="utf-8"))
good=[x for x in d if x.get("imgs") and len(x["imgs"])>0]
json.dump(good,open(r"E:\mvideo\MvideoERP\work\hat_b2input_clean.json","w",encoding="utf-8"),ensure_ascii=False)
print(len(d),"->",len(good))
