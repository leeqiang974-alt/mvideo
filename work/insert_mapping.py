import sqlite3, datetime
db = r"C:\MvideoERP\mvideo_erp.db"
con = sqlite3.connect(db); cur = con.cursor()
now = datetime.datetime.now().isoformat(timespec="seconds")
rows = [
    (17027899, "Бижутерия (броши/серьги/браслеты/брелоки)", 594040301,
     "Одежда > Бижутерия > Брошь", "INF-305107", "confirmed"),
]
for ozc, ozn, grp, grpn, inf, st in rows:
    cur.execute("""INSERT OR REPLACE INTO category_mappings
        (ozon_category_id, ozon_category_name, mv_group_id, mv_group_name, mv_infomodel_id, status, created_at)
        VALUES (?,?,?,?,?,?,?)""", (ozc, ozn, grp, grpn, inf, st, now))
con.commit()
print("mappings now:")
for r in cur.execute("SELECT id, ozon_category_id, mv_group_id, mv_infomodel_id, status FROM category_mappings"):
    print(" ", r)
con.close()
