import sqlite3
c=sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db")
c.execute("UPDATE category_mappings SET status='confirmed', mv_group_name='服装>包袋>行李箱' WHERE ozon_category_id='17027904'")
c.commit()
print(c.execute("SELECT status,COUNT(*) FROM category_mappings GROUP BY status").fetchall())
c.close()
