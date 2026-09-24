import json
d=json.load(open(r'C:\MvideoERP\work\pushed_done.json'))
# remove None entries
d=[x for x in d if x is not None]
json.dump(d,open(r'C:\MvideoERP\work\pushed_done.json','w'))
print('clean',len(d))
