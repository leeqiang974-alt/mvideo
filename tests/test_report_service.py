"""Tests for v0.4.0 report_service: batch_report + readback_verify.

Uses an in-memory SQLite session (from conftest) and a fake Omni that returns
preset price/info and stock/info payloads — no network, no real writes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.models import ItemStatus, MigrationBatch, MigrationItem
from backend.app.pipeline import report_service as rs


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _seed_batch(session, n_by_status: dict[str, int]) -> MigrationBatch:
    """Create a batch with n items per status."""
    batch = MigrationBatch(batch_ref=f"rep-{abs(hash(str(n_by_status))) % 100000}",
                           total_count=sum(n_by_status.values()))
    session.add(batch)
    session.flush()
    idx = 0
    for status, count in n_by_status.items():
        for _ in range(count):
            item = MigrationItem(
                batch_id=batch.id,
                ozon_product_id=9000 + idx,
                offer_id=f"SKU-REP-{idx}",
                name=f"Rep product {idx}",
                mv_product_id=f"PID-{idx}" if status in (
                    ItemStatus.PRODUCT_MATCHED, ItemStatus.PRICED, ItemStatus.STOCKED,
                ) else "",
                price_rub=Decimal("100.00"),
                stock=10,
                price_set=(status == ItemStatus.PRICED or status == ItemStatus.STOCKED),
                stock_set=(status == ItemStatus.STOCKED),
                status=status,
                last_error="bang!" if status == ItemStatus.NEEDS_REVIEW else "",
            )
            session.add(item)
            idx += 1
    session.commit()
    return batch


class FakeOmniReadback:
    """Fake OMNI client for readback_verify: preset price/stock maps."""

    def __init__(self, price_map: dict[str, int] | None = None,
                 stock_map: dict[str, int] | None = None) -> None:
        self._prices = price_map or {}
        self._stocks = stock_map or {}
        self.price_filters: list[dict] = []
        self.stock_filters: list[dict] = []

    def price_info(self, filter, *, cursor=None, limit=500):
        self.price_filters.append(filter)
        return {"prices": [{"product_id": pid, "price": p}
                           for pid, p in self._prices.items()]}

    def stock_info(self, filter, *, cursor=None, limit=500):
        self.stock_filters.append(filter)
        return {"stocks": [{"product_id": pid, "count": c}
                           for pid, c in self._stocks.items()]}


# --------------------------------------------------------------------------- #
# batch_report
# --------------------------------------------------------------------------- #
def test_batch_report_counts(memory_session):
    batch = _seed_batch(memory_session, {
        ItemStatus.STOCKED: 3,
        ItemStatus.PRODUCT_MATCHED: 2,
        ItemStatus.NEEDS_REVIEW: 1,
        ItemStatus.QUEUED: 1,
    })
    rep = rs.batch_report(memory_session, batch.id)
    assert rep["total_count"] == 7
    assert rep["by_status"][ItemStatus.STOCKED] == 3
    assert rep["by_status"][ItemStatus.PRODUCT_MATCHED] == 2
    assert rep["by_status"][ItemStatus.NEEDS_REVIEW] == 1
    # product_matched + priced + stocked rows have mv_product_id
    assert rep["mapped_product_id"] == 5  # 2 product_matched + 3 stocked
    assert rep["priced"] == 3  # all 3 stocked rows have price_set=True
    assert rep["stocked"] == 3
    assert rep["needs_review_count"] == 1
    assert rep["needs_review"][0]["offer_id"].startswith("SKU-REP-")
    assert rep["needs_review"][0]["last_error"] == "bang!"


def test_batch_report_missing_batch(memory_session):
    with pytest.raises(LookupError):
        rs.batch_report(memory_session, 99999)


# --------------------------------------------------------------------------- #
# readback_verify
# --------------------------------------------------------------------------- #
def test_readback_all_matched(memory_session):
    # v0.6.3: 100 CNY * 1.1 * 12 = 1320 RUB = 132000 kopecks; stock fixed 999.
    items = [
        MigrationItem(mv_product_id="PID-A", price_rub=Decimal("100.00"), stock=10,
                      offer_id="O-A"),
        MigrationItem(mv_product_id="PID-B", price_rub=Decimal("100.00"), stock=10,
                      offer_id="O-B"),
    ]
    omni = FakeOmniReadback(
        price_map={"PID-A": 132000, "PID-B": 132050},  # within 1 RUB tolerance
        stock_map={"PID-A": 999, "PID-B": 999},
    )
    v = rs.readback_verify(omni, items, rate=12.0, default_stock=0,
                           warehouse_location="WH")
    assert v["checked"] == 2
    assert len(v["matched"]) == 2
    assert v["mismatch"] == []
    assert v["missing"] == []


def test_readback_price_mismatch(memory_session):
    items = [
        MigrationItem(mv_product_id="PID-C", price_rub=Decimal("100.00"), stock=10,
                      offer_id="O-C"),
    ]
    # expected 132000 kopecks (v0.6.3), remote says 99999 -> mismatch
    omni = FakeOmniReadback(
        price_map={"PID-C": 99999},
        stock_map={"PID-C": 999},
    )
    v = rs.readback_verify(omni, items, rate=12.0, default_stock=0,
                           warehouse_location="WH")
    assert v["checked"] == 1
    assert v["matched"] == []
    assert len(v["mismatch"]) == 1
    assert v["mismatch"][0]["field"] == "price"
    assert v["mismatch"][0]["expected_kopecks"] == 132000
    assert v["mismatch"][0]["actual_kopecks"] == 99999


def test_readback_stock_mismatch(memory_session):
    items = [
        MigrationItem(mv_product_id="PID-D", price_rub=Decimal("100.00"), stock=10,
                      offer_id="O-D"),
    ]
    omni = FakeOmniReadback(
        price_map={"PID-D": 132000},
        stock_map={"PID-D": 10},
    )
    v = rs.readback_verify(omni, items, rate=12.0, default_stock=0,
                           warehouse_location="WH")
    assert len(v["mismatch"]) == 1
    assert v["mismatch"][0]["field"] == "stock"
    assert v["mismatch"][0]["expected_count"] == 999
    assert v["mismatch"][0]["actual_count"] == 10


def test_readback_missing_in_omni(memory_session):
    items = [
        MigrationItem(mv_product_id="PID-GHOST", price_rub=Decimal("100.00"),
                      stock=10, offer_id="O-G"),
    ]
    omni = FakeOmniReadback(price_map={}, stock_map={})
    v = rs.readback_verify(omni, items, rate=12.0, default_stock=0,
                           warehouse_location="WH")
    assert v["checked"] == 1
    # both price and stock absent -> classified as missing (not_found_in_omni)
    assert len(v["missing"]) == 1
    assert v["missing"][0]["reason"] == "not_found_in_omni"
    assert v["mismatch"] == []
    assert v["matched"] == []


def test_readback_no_items(memory_session):
    omni = FakeOmniReadback()
    v = rs.readback_verify(omni, [])
    assert v["checked"] == 0
    assert v["matched"] == []
    assert v["mismatch"] == []
    assert v["missing"] == []


def test_readback_omni_error_does_not_raise(memory_session):
    class BrokenOmni:
        def price_info(self, *a, **kw):
            raise RuntimeError("boom")
        def stock_info(self, *a, **kw):
            raise RuntimeError("boom")

    items = [
        MigrationItem(mv_product_id="PID-X", price_rub=Decimal("1.00"), stock=1,
                      offer_id="O-X"),
    ]
    v = rs.readback_verify(BrokenOmni(), items, rate=12.0, default_stock=0)
    assert v["checked"] == 1
    # both price and stock not found -> mismatch entries (not raise)
    assert isinstance(v["mismatch"], list)
