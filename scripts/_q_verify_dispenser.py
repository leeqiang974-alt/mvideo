# -*- coding: utf-8 -*-
"""回读验证 out_dispenser_sellersku0002.xlsx 第5行填充情况。"""
import openpyxl

wb = openpyxl.load_workbook(r"E:\mvideo\MvideoERP\work\out_dispenser_sellersku0002.xlsx", read_only=False)
ws = wb["Шаблон для загрузки товаров"]
labels = {
    1: "barcode", 2: "name", 3: "brand", 4: "dbs", 5: "fbs", 6: "fbm",
    7: "model", 8: "color", 9: "sku", 10: "vendor", 11: "country",
    12: "warranty", 13: "shelf", 14: "len", 15: "wid", 16: "hei", 17: "weight",
    43: "vertical", 44: "fragile", 45: "nds", 48: "h_cm", 49: "d_cm", 50: "w_cm",
    51: "model2", 52: "band_mm", 58: "blade", 62: "desc", 64: "w_kg",
    65: "purpose", 70: "body", 73: "color2", 74: "qty", 76: "main_photo",
}
for c, lab in labels.items():
    v = ws.cell(row=5, column=c).value
    print(f"C{c} {lab}: {str(v)[:90]}")
