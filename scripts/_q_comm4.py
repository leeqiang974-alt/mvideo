# -*- coding: utf-8 -*-
import openpyxl

wb = openpyxl.load_workbook(r"E:\mvideo\MvideoERP\work\app1_commission.xlsx", read_only=True)
ws = wb["Комиссии"]
hits = []
for row in ws.iter_rows(values_only=True):
    vals = [str(v) for v in row if v is not None]
    line = " | ".join(vals)
    low = line.lower()
    if "станок" in low or "ленточн" in low:
        hits.append(line)
print("STANOK hits:", len(hits))
for h in hits[:30]:
    print(h[:200])
