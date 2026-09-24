"""CNY -> RUB conversion for OMNI price updates (v0.3).

Ozon source prices are in CNY. The M.Video OMNI endpoint
``/v1/product/price/update`` accepts ``currency`` in its contract as
``RUB|BYN|KZT|EUR|USD|CNY`` but the doc explicitly states ONLY ``RUB`` is
honored by ЛКП. So we convert CNY -> RUB with the configured multiplier
``MV_RUB_RATE`` (default 12.0, override via env / live FX).

This module is pure and dependency-free (Decimal) so it is trivial to unit
test. It never reads or prints secrets.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .config import get_settings

# v0.6.3 pricing rules locked by user:
#   1. sell price = Ozon CNY * 1.1 (markup +10%) * MV_RUB_RATE
#   2. old (strikethrough) price = sell price * 2
#   3. stock fixed at 999 (ignore real Ozon stock)
PRICE_MARKUP = Decimal("1.1")
OLD_PRICE_MULT = Decimal("2")
MV_FIXED_STOCK = 999


def _default_rate() -> Decimal:
    try:
        return Decimal(str(get_settings().mv_rub_rate))
    except Exception:  # noqa: BLE001 - config missing -> safe default
        return Decimal("12.0")


def cny_to_rub(cny_amount: float | str | Decimal, rate: float | str | Decimal | None = None) -> Decimal:
    """Convert a CNY amount to RUB, rounded to 2 kopecks (HALF_UP).

    >>> cny_to_rub("119.00", "12.0")
    Decimal('1428.00')
    """
    cny = Decimal(str(cny_amount or "0"))
    r = Decimal(str(rate)) if rate is not None else _default_rate()
    return (cny * r).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_price_item(
    offer_id: str,
    cny_price: float | str | Decimal,
    product_id: str | int = "",
    rate: float | str | Decimal | None = None,
) -> dict:
    """Build one OMNI ``PriceUpdateItem`` (v0.6.3 pricing rules).

    - sell price (kopecks) = CNY * 1.1 (+10% markup) * MV_RUB_RATE * 100.
    - ``old_price`` (strikethrough) = sell price * 2, same kopecks.
    """
    rub = cny_to_rub(cny_price, rate)
    rub_markup = (rub * PRICE_MARKUP).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    kopecks = int((rub_markup * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))
    old_kopecks = kopecks * int(OLD_PRICE_MULT)
    item: dict = {
        "product_id": str(product_id).strip() if str(product_id or "").strip() else str(offer_id).strip(),
        "price": kopecks,
        "old_price": old_kopecks,
    }
    if str(offer_id or "").strip():
        item["offer_id"] = str(offer_id).strip()
    return item


def build_stock_item(
    offer_id: str,
    quantity: int | None = None,
    product_id: str | int = "",
    location_id: str | int = "",
) -> dict:
    """Build one OMNI ``StockUpdateItem``.

    v0.6.3: stock is FIXED at MV_FIXED_STOCK=999 regardless of Ozon real
    stock; ``quantity`` is accepted for signature compat but ignored.
    """
    item: dict = {
        "product_id": str(product_id).strip() if str(product_id or "").strip() else str(offer_id).strip(),
        "count": MV_FIXED_STOCK,
    }
    if str(location_id or "").strip():
        item["location_id"] = str(location_id).strip()
    return item
