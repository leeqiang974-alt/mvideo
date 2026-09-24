import sqlite3
c=sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
rows=[("17027907","食品容器","","","首页>餐具>食品容器、午餐盒","confirmed"),
      ("17028973","万花筒","","","儿童用品>儿童玩具>万花筒","confirmed"),
      ("17028711","安全背心","","","","needs_review")]
for r in rows:
    c.execute("INSERT OR IGNORE INTO category_mappings (ozon_category_id,ozon_category_name,mv_group_id,mv_infomodel_id,mv_group_name,status,created_at) VALUES (?,?,?,?,?,? ,datetime('now'))",r)
c.commit()
print(c.execute("SELECT status,COUNT(*) FROM category_mappings GROUP BY status").fetchall())
c.close()
