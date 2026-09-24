import sqlite3, datetime
db=r"C:\MvideoERP\mvideo_erp.db"
con=sqlite3.connect(db); cur=con.cursor()
now=datetime.datetime.now().isoformat(timespec="seconds")
rows=[
 ("2842763591","SKU00164-NR11969",403161274),
 ("2842836715","SKU00165-NR90353",403161275),
 ("2842836952","SKU00165-NR90352",403161276),
 ("2842874862","SKU00166-NR12677",403161277),
 ("2842874880","SKU00166-HX2663",403161278),
]
for ozid,offer,pid in rows:
    cur.execute("""INSERT INTO migration_items
      (batch_id,ozon_product_id,offer_id,name,brand,ozon_category_id,ozon_category_name,
       attributes_json,images_json,source_barcode,mv_group_id,mv_infomodel_id,mv_material_id,
       mv_barcode,mv_tn_ved,mv_nds,status,moderation_status,moderation_errors,quality_report,
       price_rub,price_set,stock,stock_set,attempts,last_error,created_at,updated_at,
       submitted_at,moderated_at,mv_product_id)
      VALUES (1,?,?, 'brooch','Нет бренда',17027899,'Бижутерия>Брошь','{}','{}','','594040301','305107','',
       '','','0','done','approved','{}','{}',343,1,999,1,0,'',?,?,?,?,?)""",
      (ozid,offer,now,now,now,now,str(pid)))
con.commit()
print("done rows:", cur.execute("SELECT COUNT(*) FROM migration_items WHERE status='done'").fetchone()[0])
con.close()
