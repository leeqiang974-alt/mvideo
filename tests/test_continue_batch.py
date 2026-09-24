"""Tests for the v0.4.0 continue_batch operational flow (dry-run).

We drive the SAME stages that ``scripts/continue_batch.py`` invokes:
  poll_mappings -> apply_price_stock(dry_run=True) -> readback_verify
  -> batch_report
with a fake OMNI client (no network, no real writes). Asserts that dry-run
never calls price_update / stock_update, that mapping_pending rows advance
to product_matched when OMNI returns them, and that the report shapes match.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.models import ItemStatus, MigrationBatch, MigrationItem
from backend.app.pipeline import migrate_service as svc
from backend.app.pipeline import report_service as rs


class FakeOmniContinue:
    """Fake OMNI supporting the full continue flow."""

    def __init__(self, offer_to_product: dict[str, str] | None = None) -> None:
        self.offer_to_product = offer_to_product or {}
        self.price_calls: list[list[dict]] = []
        self.stock_calls: list[list[dict]] = []

    # poll_mappings uses iter_mappings
    def iter_mappings(self, filter=None):
        for oid, pid in self.offer_to_product.items():
            yield {"offer_id": oid, "product_id": pid}

    # apply_price_stock uses these (must NOT be called in dry-run)
    def price_update(self, items, currency="RUB"):
        self.price_calls.append(list(items))
        return {"failed": []}

    def stock_update(self, items):
        self.stock_calls.append(list(items))
        return {"failed": []}

    # readback_verify uses these
    def price_info(self, filter, *, cursor=None, limit=500):
        pids = filter.get("product_id", []) if isinstance(filter, dict) else []
        return {"prices": [
            {"product_id": p, "price": 132000} for p in pids
        ]}

    def stock_info(self, filter, *, cursor=None, limit=500):
        pids = filter.get("product_id", []) if isinstance(filter, dict) else []
        return {"stocks": [
            {"product_id": p, "count": 999} for p in pids
        ]}


def _seed(memory_session, n=4):
    batch = MigrationBatch(batch_ref="cont-test", total_count=n)
    memory_session.add(batch)
    memory_session.flush()
    for i in range(n):
        memory_session.add(MigrationItem(
            batch_id=batch.id,
            ozon_product_id=5000 + i,
            offer_id=f"SKU-C-{i}",
            name=f"Continue product {i}",
            mv_product_id=f"PID-C-{i}" if i >= 1 else "",  # last row already matched
            price_rub=Decimal("100.00"),  # CNY -> 1200 RUB at rate 12
            stock=10,
            status=(ItemStatus.PRODUCT_MATCHED if i >= 2
                    else ItemStatus.TEMPLATE_UPLOADED),
        ))
    memory_session.commit()
    return batch


def test_continue_dry_run_no_writes(memory_session):
    batch = _seed(memory_session, n=4)
    omni = FakeOmniContinue({
        "SKU-C-0": "PID-C-0",
        "SKU-C-1": "PID-C-1",
    })

    # Stage 1: poll mappings (the 2 template_uploaded rows become product_matched)
    mp = svc.poll_mappings(memory_session, omni, batch_id=batch.id)
    assert mp["product_matched"] == 2
    assert mp["mapping_pending"] == 0

    # Stage 2: apply price/stock DRY-RUN -> no real writes
    ps = svc.apply_price_stock(memory_session, omni, batch_id=batch.id, dry_run=True)
    assert ps["would_price"] == 4
    assert ps["would_stock"] == 4
    assert ps["priced"] == 0
    assert ps["stocked"] == 0
    # CRITICAL: dry-run must NOT have called price_update / stock_update
    assert omni.price_calls == []
    assert omni.stock_calls == []

    # Stage 3: readback verify (all 4 now have mv_product_id)
    items = memory_session.query(MigrationItem).filter(
        MigrationItem.batch_id == batch.id
    ).all()
    rb = rs.readback_verify(omni, items, rate=12.0, default_stock=10,
                            warehouse_location="WH")
    assert rb["checked"] == 4
    assert len(rb["matched"]) == 4  # 132000 kopecks expected (v0.6.3), 132000 actual

    # Stage 4: batch report
    rep = rs.batch_report(memory_session, batch.id)
    assert rep["total_count"] == 4
    assert rep["mapped_product_id"] == 4
    # No rows were priced/stocked (dry-run), so priced/stocked counters = 0
    assert rep["priced"] == 0
    assert rep["stocked"] == 0


def test_continue_apply_writes_matches_dry_run_structure(memory_session):
    """With --apply-writes, the same stages run but actually call OMNI."""
    # Seed both as TEMPLATE_UPLOADED; poll_mappings resolves both to product_matched.
    batch = MigrationBatch(batch_ref="cont-apply", total_count=2)
    memory_session.add(batch)
    memory_session.flush()
    for i in range(2):
        memory_session.add(MigrationItem(
            batch_id=batch.id,
            ozon_product_id=6000 + i,
            offer_id=f"SKU-A-{i}",
            name=f"Apply product {i}",
            mv_product_id="",
            price_rub=Decimal("100.00"),
            stock=10,
            status=ItemStatus.TEMPLATE_UPLOADED,
        ))
    memory_session.commit()

    omni = FakeOmniContinue({
        "SKU-A-0": "PID-A-0",
        "SKU-A-1": "PID-A-1",
    })

    mp = svc.poll_mappings(memory_session, omni, batch_id=batch.id)
    assert mp["product_matched"] == 2
    assert mp["mapping_pending"] == 0

    ps = svc.apply_price_stock(memory_session, omni, batch_id=batch.id, dry_run=False)
    assert ps["priced"] == 2
    assert ps["stocked"] == 2
    assert len(omni.price_calls) == 1
    assert len(omni.stock_calls) == 1

    rep = rs.batch_report(memory_session, batch.id)
    assert rep["priced"] == 2
    assert rep["stocked"] == 2
