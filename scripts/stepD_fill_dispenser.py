# -*- coding: utf-8 -*-
"""Fill the M.Video 'Диспенсер для монтажной ленты' template for sellersku0002.

Source data: Ozon product 1237743084 (Станок для резки ленты Санрио):
  - бренд: Нет бренда, артикул TQBSM1
  - материал: Силикон, цвет: фиолетовый, страна: Китай
  - размеры: 13x6.5x8 cm (width/height/depth from v4), вес 0.4 kg
  - описание из атрибута 4191
  - 1 изображение (OSS URL)

Column map (Dispenser template, 95 cols):
  C1 barcode* | C2 name* | C3 brand* | C4 dbs* | C5 fbs* | C6 fbm* |
  C7 model* | C8 color* | C9 sku_code* | C10 vendor_code* | C11 country* |
  C12 warranty* | C13 shelf_life* | C14 len* | C15 wid* | C16 hei* | C17 weight* |
  C43 vertical* | C44 fragile* | C45 nds* | C46 tnved |
  C48 height_cm | C49 depth_cm | C50 width_cm | C51 model | C52 band_width_mm |
  C53 hub_diam_mm | C55 max_roll_diam_cm | C57 features | C58 blade_material |
  C62 description | C63 pack_type | C64 weight_kg | C65 purpose | C70 body_material |
  C73 color | C74 qty | C75 kit |
  C76 main_photo* | C77..C90 photos 1..14 | C91..C95 docs
"""
import shutil
from pathlib import Path

import openpyxl

ROOT = Path(r"E:\mvideo\MvideoERP")
TPL = ROOT / "work" / "template_dispenser.xlsx"
OUT = ROOT / "work" / "out_dispenser_sellersku0002.xlsx"

DESC = ("Станок для резки ленты Санрио. Бренд: Другое. Материал: Силикон. "
        "Артикул: TQBSM1. Модель: TQBSM1. Масса нетто: 150 г. "
        "Подходит для ширины ленты до 20 мм. Применимый случай: общего назначения. "
        "Цвет: фиолетовый. Страна производства: Китай.")

def main() -> int:
    shutil.copy2(TPL, OUT)
    wb = openpyxl.load_workbook(OUT)
    ws = wb["Шаблон для загрузки товаров"]
    r = 5

    ws.cell(row=r, column=1, value="Сгенерировать")          # barcode
    ws.cell(row=r, column=2, value="Станок для резки ленты Санрио")  # name
    ws.cell(row=r, column=3, value="Нет бренда")              # brand
    ws.cell(row=r, column=4, value="Нет")                     # DBS
    ws.cell(row=r, column=5, value="Да")                      # FBS
    ws.cell(row=r, column=6, value="Нет")                     # FBM
    ws.cell(row=r, column=7, value="TQBSM1")                  # model
    ws.cell(row=r, column=8, value="фиолетовый")              # color
    ws.cell(row=r, column=9, value="sellersku0002")           # sku_code
    ws.cell(row=r, column=10, value="TQBSM1")                 # vendor_code
    ws.cell(row=r, column=11, value="Китай")                  # country
    ws.cell(row=r, column=12, value="Нет")                    # warranty
    ws.cell(row=r, column=13, value=0)                        # shelf_life
    ws.cell(row=r, column=14, value=13.0)                     # length cm (pack)
    ws.cell(row=r, column=15, value=6.5)                      # width cm
    ws.cell(row=r, column=16, value=8.0)                      # height cm
    ws.cell(row=r, column=17, value=0.4)                      # weight kg
    ws.cell(row=r, column=43, value="Нет")                    # vertical only
    ws.cell(row=r, column=44, value="Нет")                    # fragile
    ws.cell(row=r, column=45, value="0")                      # NDS
    ws.cell(row=r, column=46, value="")                       # TNVED (empty)
    ws.cell(row=r, column=48, value=8.0)                      # height cm (char)
    ws.cell(row=r, column=49, value=6.5)                      # depth cm
    ws.cell(row=r, column=50, value=13.0)                     # width cm
    ws.cell(row=r, column=51, value="TQBSM1")                 # model
    ws.cell(row=r, column=52, value=20)                       # band width mm
    ws.cell(row=r, column=55, value="")                       # max roll diam
    ws.cell(row=r, column=57, value="Общего назначения")      # features
    ws.cell(row=r, column=58, value="Силикон")                # blade material
    ws.cell(row=r, column=62, value=DESC)                     # description
    ws.cell(row=r, column=63, value="")                       # pack type
    ws.cell(row=r, column=64, value=0.4)                      # weight kg
    ws.cell(row=r, column=65, value="Общего назначения")      # purpose
    ws.cell(row=r, column=70, value="Силикон")                # body material
    ws.cell(row=r, column=73, value="фиолетовый")             # color
    ws.cell(row=r, column=74, value=1)                        # qty
    ws.cell(row=r, column=75, value="1 шт")                   # kit

    # Main photo from OSS manifest (sellersku0002 -> url)
    import json
    man = json.loads((ROOT / "work" / "oss_urls_dispenser.json").read_text(encoding="utf-8"))
    main_url = ""
    for v in man:
        if v.get("offer_id") == "sellersku0002" and v.get("images"):
            main_url = v["images"][0]["url"]
            break
    if main_url:
        ws.cell(row=r, column=76, value=main_url)
    else:
        print("WARN: no OSS url for sellersku0002 in manifest; main photo left empty")

    wb.save(OUT)
    print(f"DONE -> {OUT}")
    print("main_photo:", main_url[:80] if main_url else "EMPTY")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
