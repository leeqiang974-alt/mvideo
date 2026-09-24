import sqlite3
con=sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db"); cur=con.cursor()
rows=[
 ("41777465","Шапка (headwear)","","服装>帽子>头饰","needs_review","path found, group_id pending"),
 ("17028743","Плюшевый брелок","","服装>首饰>钥匙扣","needs_review","path found, group_id pending"),
 ("17028749","Автобрелок/котик","","汽车用品>配件及装备>汽车钥匙扣","needs_review","path found, group_id pending"),
 ("17028959","Интим-товары (вибратор)","","","needs_review","ADULT - M.Video likely rejects, do not upload"),
 ("200001479","Эротическое белье","","","needs_review","ADULT - M.Video likely rejects, do not upload"),
]
for cid,cname,gg,gn,st,note in rows:
    cur.execute("""INSERT INTO category_mappings (ozon_category_id,ozon_category_name,mv_group_id,mv_infomodel_id,mv_group_name,status,created_at)
                   VALUES (?,?,?,?,?,?,datetime('now'))""",(cid,cname,gg,"",gn,st))
con.commit()
print("mappings now:", cur.execute("SELECT status,COUNT(*) FROM category_mappings GROUP BY status").fetchall())
con.close()
