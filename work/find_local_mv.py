import sqlite3, os, glob, shutil, tempfile
base = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
hits = []
for hist in glob.glob(os.path.join(base, "*", "History")):
    try:
        tmp = os.path.join(tempfile.gettempdir(), "hcopy.db")
        shutil.copy2(hist, tmp)
        con = sqlite3.connect(tmp); cur = con.cursor()
        cur.execute("SELECT url, title FROM urls WHERE url LIKE '%mvideo%' OR url LIKE '%/mpa/%' ORDER BY last_visit_time DESC LIMIT 40")
        for u, t in cur.fetchall():
            hits.append((os.path.basename(os.path.dirname(hist)), (t or "")[:45], u[:150]))
        con.close()
    except Exception as e:
        print("skip", hist, e)
seen = set()
for p, t, u in hits:
    if u in seen: continue
    seen.add(u); print(p, "|", t, "|", u)
