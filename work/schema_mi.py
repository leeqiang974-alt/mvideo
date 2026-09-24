import sqlite3
con=sqlite3.connect(r"C:\MvideoERP\mvideo_erp.db"); cur=con.cursor()
for r in cur.execute("PRAGMA table_info(migration_items)"):
    print(r)
con.close()
