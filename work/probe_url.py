import openpyxl, sys
sys.stdout.reconfigure(encoding="utf-8")
wb=openpyxl.load_workbook(r"E:\mvideo\MvideoERP\work\downloads\mv_upload_brooch_pilot.xlsx")
ws=wb["Шаблон для загрузки товаров"]
print("pilot:",str(ws.cell(5,75).value)[:200])
