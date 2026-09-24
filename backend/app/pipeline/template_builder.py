"""Build the M.Video Excel-import rows from MigrationItems (v0.3).

This is the programmatic twin of scripts/stepD_fill_template.py (SKU00259,
proven live). OMNI has NO product-create endpoint, so cards are created by
filling M.Video's 90-column template and uploading it to
``/mpa/products/import``. ``build_template_rows`` turns MigrationItem rows
(already quality-gated + images mirrored to OSS) into the ordered cell payload
the template expects.

The function returns plain dicts (column index -> value) so it is pure and
unit-testable without openpyxl. ``write_template_xlsx`` applies those rows to
the downloaded template workbook (openpyxl imported lazily; data rows start at
row 5, rows 1-4 are header blocks).
"""

from __future__ import annotations

import logging
import re
import shutil
from typing import Any, Iterable

log = logging.getLogger("mvideo.template")

# 1-based column layout, proven against the live SKU00259 upload.
COLS: dict[str, int] = {
    "barcode": 1, "name": 2, "brand": 3,
    "dbs": 4, "fbs": 5, "fbm": 6,
    "model": 7, "color": 8, "sku_code": 9, "vendor_code": 10,
    "country": 11, "warranty": 12, "shelf_life": 13,
    "length": 14, "width": 15, "height": 16, "weight": 17,
    "vertical": 43, "fragile": 44, "nds": 45,
    "material": 55, "material_base": 57, "description": 58,
    "main_photo": 71,
}
PHOTO_COLS = list(range(72, 86))  # photos 1..14 -> cols 72..85
DATA_START_ROW = 5
SHEET_NAME = "Шаблон для загрузки товаров"


def _g(obj: Any, key: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clean_html(t: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", t or "")
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:1500]


def build_template_rows(
    items: Iterable[Any],
    *,
    supply_scheme: str = "FBS",
    country: str = "Китай",
) -> list[dict[int, Any]]:
    """Turn MigrationItem rows into ordered {column_index: value} dicts.

    Each item must carry: offer_id, name, brand, mv_barcode/source_barcode,
    mv_color (optional), description, and ``oss_images_json`` = [{url}...].
    Barcode column is set to "Сгенерировать" (M.Video generates EAN18).
    """
    rows: list[dict[int, Any]] = []
    fbs = "Да" if supply_scheme.upper() == "FBS" else "Нет"
    dbs = "Да" if supply_scheme.upper() == "DBS" else "Нет"

    for it in items:
        offer = str(_g(it, "offer_id", "")).strip()
        name = str(_g(it, "name", "")).strip()
        brand = str(_g(it, "brand", "")).strip() or "Нет бренда"
        color = str(_g(it, "color", "")).strip() or "белый"
        desc_raw = _g(it, "mv_description", "") or _g(it, "description", "")
        desc = _clean_html(str(desc_raw)) if desc_raw else "Товар"
        weight = _g(it, "weight", "")

        row: dict[int, Any] = {
            COLS["barcode"]: "Сгенерировать",
            COLS["name"]: name,
            COLS["brand"]: brand,
            COLS["dbs"]: dbs,
            COLS["fbs"]: fbs,
            COLS["fbm"]: "Нет",
            COLS["model"]: name,
            COLS["color"]: color,
            COLS["sku_code"]: offer,
            COLS["vendor_code"]: offer,
            COLS["country"]: country,
            COLS["warranty"]: "Нет",
            COLS["shelf_life"]: 0,
            COLS["vertical"]: "Нет",
            COLS["fragile"]: "Нет",
            COLS["nds"]: "0",
            COLS["description"]: desc,
        }
        # cols 14-17: pack dimensions (cm / kg), required by M.Video moderation.
        for col_key, attr in (
            ("length", "mv_length_cm"),
            ("width", "mv_width_cm"),
            ("height", "mv_height_cm"),
            ("weight", "mv_weight_kg"),
        ):
            val = _g(it, attr, 0)
            if val not in (None, "", 0):
                row[COLS[col_key]] = val

        images = _g(it, "oss_images_json", []) or []
        urls = [str(im.get("url", "")) for im in images if isinstance(im, dict) and im.get("url")]
        if urls:
            row[COLS["main_photo"]] = urls[0]
            for i, url in enumerate(urls[1:15]):
                row[PHOTO_COLS[i]] = url
        rows.append(row)
    return rows


def write_template_xlsx(
    rows: list[dict[int, Any]],
    template_path: str,
    out_path: str,
) -> str:
    """Apply built rows onto the downloaded template workbook. openpyxl lazy."""
    import openpyxl  # lazy: not needed for pure row building / unit tests

    shutil.copy2(template_path, out_path)
    wb = openpyxl.load_workbook(out_path)
    ws = wb[SHEET_NAME]
    for offset, row in enumerate(rows):
        r = DATA_START_ROW + offset
        for col_idx, value in row.items():
            ws.cell(row=r, column=int(col_idx), value=value)
    wb.save(out_path)
    log.info("wrote %d template rows -> %s", len(rows), out_path)
    return out_path
