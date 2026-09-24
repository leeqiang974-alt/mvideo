# -*- coding: utf-8 -*-
"""Tests for app.currency (v0.3): CNY -> RUB conversion + OMNI item build."""

from decimal import Decimal

from app.currency import build_price_item, build_stock_item, cny_to_rub


class TestCnyToRub:
    def test_100_cny_at_rate_12(self):
        assert cny_to_rub(100.0, "12.0") == Decimal("1200.00")

    def test_half_up_rounding(self):
        # 119.90 * 12.345 = 1480.1655 -> HALF_UP -> 1480.17
        assert cny_to_rub("119.90", "12.345") == Decimal("1480.17")

    def test_zero(self):
        assert cny_to_rub(0, "12.0") == Decimal("0.00")


class TestBuildPriceItem:
    def test_amount_is_kopecks_int(self):
        # v0.6.3: CNY*1.1*rate*100. 100*1.1*12=1320 RUB -> 132000 kopecks.
        item = build_price_item("SKU00259", 100.0, rate="12.0")
        assert item["offer_id"] == "SKU00259"
        assert item["price"] == 132000  # 1320.00 RUB = 132000 kopecks
        assert item["old_price"] == 264000  # strikethrough = price*2
        # currency lives on the request envelope, never per-item.
        assert "currency" not in item

    def test_strips_offer(self):
        item = build_price_item("  SKU1  ", 10.0, rate="12.0")
        assert item["offer_id"] == "SKU1"
        assert item["price"] == 13200  # 10*1.1*12=132 RUB = 13200 kopecks

    def test_exact_sku00259_case(self):
        # 119.00 CNY * 1.1 * 12.0 = 1570.80 RUB = 157080 kopecks
        item = build_price_item("SKU00259", "119.00", rate="12.0")
        assert item["price"] == 157080
        assert item["old_price"] == 314160


class TestBuildStockItem:
    def test_basic(self):
        # v0.6.3: stock fixed 999 regardless of passed quantity.
        item = build_stock_item("SKU1", 7, product_id="P1")
        assert item == {"product_id": "P1", "count": 999}

    def test_with_location(self):
        item = build_stock_item("SKU1", 3, product_id="P1", location_id="R-123")
        assert item["location_id"] == "R-123"
        assert item["count"] == 999

    def test_offer_fallback_when_no_product_id(self):
        item = build_stock_item("SKU1", 5)
        assert item["product_id"] == "SKU1"
        assert item["count"] == 999
