import shutil, sqlite3, tempfile, os, glob, time

base = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"
hits = []
for hist in glob.glob(os.path.join(base, "*", "History")):
    prof = os.path.basename(os.path.dirname(hist))
    tmp = os.path.join(tempfile.gettempdir(), "h.db")
    try:
        shutil.copy2(hist, tmp)
    except Exception as e:
        continue
    try:
        con = sqlite3.connect(tmp); cur = con.cursor()
        cur.execute("SELECT url, title FROM urls WHERE url LIKE '%/mpa/%' OR url LIKE '%sellers.mvideo%' OR url LIKE '%mvideo%'")
        for url, title in cur.fetchall():
            if "google" in url: continue
            hits.append((prof, (title or "")[:45], url[:140]))
        con.close()
    except Exception as e:
        print("err", prof, e)
seen = set()
for prof, t, u in hits:
    if u in seen: continue
    seen.add(u)
    print(prof, "|", t, "|", u)
