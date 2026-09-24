import openpyxl, glob, os, json
os.chdir(r"C:\MvideoERP\work")
out = {}
for pat, key in [("mv_upload_brooch_b3_fix*.xlsx","b3_fix"), ("mv_upload_brooch_pilot*.xlsx","pilot")]:
    fs = sorted(glob.glob(pat))
    if not fs:
        out[key] = {"file": None}
        continue
    f = fs[0]
    wb = openpyxl.load_workbook(f, read_only=True)
    # find data sheet
    ws = None
    for s in wb.worksheets:
        if "Шаблон" in s.title or "загруз" in s.title.lower():
            ws = s; break
    if ws is None: ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    # header row
    hdr = rows[1] if len(rows)>1 else rows[0]
    # find image column: header containing "Фото" or "главн"
    img_cols = [i for i,h in enumerate(hdr) if h and ("фото" in str(h).lower() or "главн" in str(h).lower())]
    samples = []
    for r in rows[2:4]:
        for c in img_cols[:2]:
            if c < len(r) and r[c]:
                samples.append(str(r[c])[:160])
    out[key] = {"file": os.path.basename(f), "img_cols": img_cols[:5], "samples": samples}
print(json.dumps(out, ensure_ascii=False, indent=1))
