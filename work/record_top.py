import sqlite3
con=sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db"); cur=con.cursor()
rows=[
 ("29183107","发圈/发饰","","服装>发饰>发圈","confirmed","path found"),
 ("17028727","地毯","","家居用品>家用纺织品>地毯","confirmed","path found"),
 ("41777465","帽子","","服装>帽子>头饰","confirmed","path found"),
 ("200001425","硅胶模/手工","","","needs_review","MV no result"),
 ("17027904","行李箱","","","needs_review","re-search чемодан"),
]
for cid,cname,gg,gn,st,note in rows:
    cur.execute("INSERT OR IGNORE INTO category_mappings (ozon_category_id,ozon_category_name,mv_group_id,mv_infomodel_id,mv_group_name,status,created_at) VALUES (?,?,?,?,?,? ,datetime('now'))",(cid,cname,gg,"",gn,st))
con.commit()
print("mappings:",cur.execute("SELECT status,COUNT(*) FROM category_mappings GROUP BY status").fetchall())
con.close()
