import shutil, sqlite3, tempfile, os
src = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data\Default\History"
tmp = os.path.join(tempfile.gettempdir(), "hist_copy.db")
shutil.copy2(src, tmp)
con = sqlite3.connect(tmp)
cur = con.cursor()
cur.execute("""SELECT url, title, last_visit_time FROM urls
               WHERE url LIKE '%mvideo%' OR url LIKE '%mv%'
               ORDER BY last_visit_time DESC LIMIT 40""")
for url, title, t in cur.fetchall():
    print(t, "|", (title or "")[:50], "|", url[:120])
con.close()
