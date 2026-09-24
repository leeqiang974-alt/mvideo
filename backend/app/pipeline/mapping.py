"""Field mapping: an Ozon product (as a MigrationItem row) -> M.Video payload.

v0.2 (2026-09-18): rebuilt against the VERIFIED live OpenAPI
(https://api.sellers.mvideo.ru/openapi/api/main, v1.5.9). The real
MaterialV2 create request is:

    POST /v2/material
    {"offerMappings": [ { OfferDtoRequest }, ... ]}   (max 50 offers)

OfferDtoRequest fields (verified):
  offerId, salesScheme (MARKETPLACE only), name, generateBarcodes (Да/Нет),
  barcodes (max 3, 13-digit numbers), brand, categoryId (leaf category id),
  model, vendorCode, color, manufacturerCountries (1 value),
  warrantyPeriod {timePeriod, timeUnit (MONTH/YEAR)},
  weightDimensions {length,width,height,weight},
  isVerticalOnly (Да/Нет), isFragile (Да/Нет), vat (0,5,7,10,22),
  tnvedCode, okpd2Code, marking (Да/Нет), fireHazardClass (4..9/Нет),
  description (<=1500), deliveryScheme ([FBS,FBM,DBS]),
  attributes [{attributeId, attributeValue}], pictures (<=15), manuals (<=5 PDF)

Category mapping persistence lives here too so the pipeline never writes
category rows directly.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ..models import CategoryMapping


def resolve_category(session, ozon_category_id: int, ozon_category_name: str = "") -> CategoryMapping | None:
    """Look up (or lazily create a draft) the Ozon->M.Video category mapping."""
    stmt = select(CategoryMapping).where(CategoryMapping.ozon_category_id == int(ozon_category_id or 0))
    row = session.execute(stmt).scalar_one_or_none()
    if row is not None:
        return row
    if not ozon_category_id:
        return None
    row = CategoryMapping(
        ozon_category_id=int(ozon_category_id),
        ozon_category_name=ozon_category_name or "",
        status="draft",
    )
    session.add(row)
    session.commit()
    return row


def _attributes_from_ozon(attrs_json: Any) -> list[dict[str, Any]]:
    """Best-effort translation of Ozon attributes -> M.Video attributes.

    Ozon attributes arrive as [{"complex_id":..,"id":..,"values":[{"value":..}]}].
    M.Video expects [{attributeId, attributeValue}]. Without a manual
    attribute mapping (Ozon attr id -> M.Video attributeId from
    /v2/dictionaries/attribute) we emit the Ozon attribute id as a hint and
    the human fills ``attribute_mappings`` before resubmit. The quality gate
    requires categoryId; attribute ids are best-effort.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(attrs_json, list):
        return out
    for a in attrs_json:
        if not isinstance(a, dict):
            continue
        values = a.get("values") or []
        if not values:
            continue
        val = values[0]
        if isinstance(val, dict):
            v = val.get("value", "")
        else:
            v = val
        out.append(
            {
                "attributeId": a.get("id", ""),
                "attributeValue": str(v),
            }
        )
    return out


def build_material_payload(
    item,
    *,
    supply_scheme: str = "FBS",
    nds: str = "USN",
) -> dict[str, Any]:
    """Assemble ONE OfferDtoRequest dict for one MigrationItem.

    The caller wraps the result in {"offerMappings": [payload]} (or passes it
    directly to MvideoClient.create_material which does the wrapping).
    """
    def _g(key, default=""):
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    images = _g("images_json", []) or []
    images = [str(u) for u in images if str(u).startswith("http")][:15]

    offer: dict[str, Any] = {
        "offerId": str(_g("offer_id", "")).strip(),
        "salesScheme": "MARKETPLACE",
        "name": str(_g("name", "")).strip(),
        "generateBarcodes": "Нет",  # we always supply our own barcodes
        "barcodes": [
            str(_g("mv_barcode", "")).strip()
            or str(_g("source_barcode", "")).strip()
        ],
        "brand": str(_g("brand", "")).strip(),
        "categoryId": int(_g("mv_group_id", 0) or 0),
        "description": str(_g("description", "")).strip()[:1500],
        "deliveryScheme": [str(supply_scheme).upper()],
        "vat": int(_g("mv_nds", 0) or 0),
        "attributes": _attributes_from_ozon(_g("attributes_json", [])),
        "pictures": images,
    }
    # Optional fields only when present (spec allows omitting them).
    model = str(_g("model", "")).strip()
    if model:
        offer["model"] = model
    vendor_code = str(_g("vendor_code", "")).strip()
    if vendor_code:
        offer["vendorCode"] = vendor_code
    color = str(_g("color", "")).strip()
    if color:
        offer["color"] = color
    tnved = str(_g("mv_tn_ved", "")).strip()
    if tnved:
        offer["tnvedCode"] = tnved
    # warranty: timePeriod integer, timeUnit MONTH/YEAR
    tp = _g("warranty_period", "")
    if tp:
        try:
            offer["warrantyPeriod"] = {"timePeriod": str(int(float(tp))), "timeUnit": "MONTH"}
        except (TypeError, ValueError):
            pass
    # dimensions: strings with one decimal separator
    dims = {
        "length": _g("dim_length", ""),
        "width": _g("dim_width", ""),
        "height": _g("dim_height", ""),
        "weight": _g("dim_weight", ""),
    }
    if any(v for v in dims.values()):
        cleaned = {}
        for k, v in dims.items():
            s = str(v or "").strip().replace(",", ".")
            if s:
                cleaned[k] = s
        if cleaned:
            offer["weightDimensions"] = cleaned
    # countries (max 1)
    countries = _g("manufacturer_countries", []) or []
    if isinstance(countries, list) and countries:
        offer["manufacturerCountries"] = [str(countries[0])]
    return offer


def build_price_payload(material_code: str, price: float, date_start: str) -> dict[str, Any]:
    """UpdatePrice item (verified): materialCode, price, currency=RUB, dateStart."""
    return {
        "materialCode": str(material_code),
        "price": float(price),
        "currency": "RUB",
        "dateStart": str(date_start),  # YYYY-MM-DD
    }


def build_stock_payload(warehouse_code: str, material_code: str, quantity: int) -> dict[str, Any]:
    """UpdateStock item (verified): warehouseCode, materialCode, quantity, unit=PIECES."""
    return {
        "warehouseCode": str(warehouse_code),
        "materialCode": str(material_code),
        "quantity": int(quantity),
        "unit": "PIECES",
    }
