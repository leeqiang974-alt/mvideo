# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import openpyxl
wb = openpyxl.load_workbook(r"C:\OzonERP\verify_tpl.xlsx", read_only=True)
ws = wb["Шаблон для загрузки товаров"]
rows = list(ws.iter_rows(min_row=1, max_row=12, values_only=True))
for i, r in enumerate(rows):
    nonempty = [(j, str(c)[:28]) for j, c in enumerate(r) if c is not None and str(c).strip()]
    print(f"R{i}: {len(nonempty)} cells:", nonempty[:8])
