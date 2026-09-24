import sqlite3
con=sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db"); cur=con.cursor()
cur.execute("""INSERT INTO category_mappings (ozon_category_id,ozon_category_name,mv_group_id,mv_infomodel_id,mv_group_name,status,created_at)
               VALUES ('17028653','Трещотка (ratchet)','','','建筑与维修>装配手动工具>棘轮扳手','needs_review',datetime('now'))""")
con.commit()
print("mappings:", cur.execute("SELECT status,COUNT(*) FROM category_mappings GROUP BY status").fetchall())
con.close()
