import json
d=json.load(open(r"E:\mvideo\MvideoERP\work\category_inventory_full.json",encoding="utf-8"))
print("rows",len(d),"total",sum(x["count"] for x in d))
for x in d[15:45]:
    print(f'{x["ozon_category_id"]:>11} {x["count"]:>5} {x["zh"] or x["ru"]}')
