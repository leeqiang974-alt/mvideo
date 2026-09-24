import openpyxl
b2=openpyxl.load_workbook(r"E:\mvideo\MvideoERP\work\downloads\mv_upload_brooch_b2.xlsx").active
for r in range(1,18):
    vals=[b2.cell(r,c).value for c in range(1,7)]
    print(r, vals)
