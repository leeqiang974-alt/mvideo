# -*- coding: utf-8 -*-
import openpyxl

wb = openpyxl.load_workbook(r"E:\mvideo\MvideoERP\work\app1_commission.xlsx", read_only=True)
ws = wb["Комиссии"]
targets = ["лент", "станок", "режущ", "ножниц"]
seen = set()
for row in ws.iter_rows(values_only=True):
    vals = [str(v) for v in row if v is not None]
    line = " | ".join(vals)
    for kw in targets:
        if kw.lower() in line.lower():
            key = line[:50]
            if key not in seen:
                seen.add(key)
                print(line[:200])
            break
