"""End-to-end tests for the v0.3 OMNI + Excel-template migration pipeline.

Uses an in-memory SQLite session + a fake OmniClient / fake OssUploader /
fake Ozon client (no network, no real price/stock write). Drives the new
state machine:
  queued -> prepared -> images_processed -> template_built
         -> template_uploaded -> mapping_pending -> product_matched
         -> priced -> stocked
and asserts the stocked count reconciles to total_count.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from PIL import Image

from backend.app import models
from backend.app.currency import build_price_item, cny_to_rub
from backend.app.models import ItemStatus, MigrationBatch, MigrationItem
from backend.app.pipeline import migrate_service as svc
from backend.app.pipeline.template_builder import build_template_rows


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeOmni:
    """Records price/stock calls; returns a mapping for every offer_id."""

    def __init__(self, offer_to_product: dict[str, str] | None = None) -> None:
        self.offer_to_product = offer_to_product or {}
        self.price_calls: list[list[dict]] = []
        self.stock_calls: list[list[dict]] = []
        self.mapping_filters: list[dict] = []

    def iter_mappings(self, filter: dict | None = None):
        self.mapping_filters.append(filter or {})
        for oid, pid in self.offer_to_product.items():
            yield {"offer_id": oid, "product_id": pid}

    def price_update(self, items, currency="RUB"):
        self.price_calls.append(list(items))
        return {"failed": []}

    def stock_update(self, items):
        self.stock_calls.append(list(items))
        return {"failed": []}

    def check_connection(self):
        return True


class FakeOss:
    def upload_image_file(self, path, key):
        return f"https://oss.example/{key}"


class FakeOzon:
    """Minimal Ozon source: one product, attributes + price."""

    def __init__(self, products):
        self._products = products

    def iter_products(self, limit=100):
        for p in self._products[:limit]:
            yield p

    def get_product_attributes(self, ids):
        pid = ids[0]
        prod = self._by_id(pid)
        return {"result": [prod]}

    def get_prices(self, ids):
        pid = ids[0]
        price = str(self._by_id(pid).get("price", "119.00"))
        return {"items": [{"price": {"price": price}}]}

    def _by_id(self, pid):
        for p in self._products:
            if int(p.get("id")) == int(pid):
                return p
        return {}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_3x4_png(tmp_path, name):
    p = tmp_path / name
    Image.new("RGB", (975, 1300), (255, 255, 255)).save(p, "PNG")
    return str(p)


def _seed_batch(session, tmp_path, n=3, *, status=ItemStatus.QUEUED, with_oss=True):
    batch = MigrationBatch(batch_ref=f"test-{n}", total_count=n)
    session.add(batch)
    session.flush()
    imgs = [_make_3x4_png(tmp_path, f"img{i}.png") for i in range(1)]
    for i in range(n):
        oss_images = (
            [{"idx": 1, "url": f"https://oss.example/sku{i:02d}/01.jpg", "key": f"sku{i:02d}/01.jpg"}]
            if with_oss else []
        )
        item = MigrationItem(
            batch_id=batch.id,
            ozon_product_id=1000 + i,
            offer_id=f"SKU-TEST-{i}",
            name=f"Test product {i}",
            brand="Acme",
            mv_group_id="100",
            mv_nds="USN",
            mv_tn_ved="01234567",
            source_barcode="4607012345678",
            images_json=imgs,
            oss_images_json=oss_images,
            price_rub=Decimal("119.00"),  # CNY source price
            mv_length_cm=13,
            mv_width_cm=6.5,
            mv_height_cm=8,
            mv_weight_kg=0.4,
            status=status,
        )
        session.add(item)
    session.commit()
    return batch


# --------------------------------------------------------------------------- #
# Currency
# --------------------------------------------------------------------------- #
def test_cny_to_rub_and_build_price_item():
    assert cny_to_rub("119.00", "12.0") == Decimal("1428.00")
    item = build_price_item("SKU-1", "119.00", rate="12.0")
    assert item["offer_id"] == "SKU-1"
    assert item["price"] == 157080  # 119*1.1*12=1570.80 RUB = 157080 kopecks (v0.6.3)
    assert item["old_price"] == 314160


# --------------------------------------------------------------------------- #
# Template rows
# --------------------------------------------------------------------------- #
def test_build_template_rows_shape():
    rows = build_template_rows(
        [
            {
                "offer_id": "SKU-1",
                "name": "Mat",
                "brand": "Acme",
                "oss_images_json": [
                    {"url": "https://oss/a.jpg"},
                    {"url": "https://oss/b.jpg"},
                ],
            }
        ]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row[1] == "Сгенерировать"          # barcode col A
    assert row[2] == "Mat"                    # name col B
    assert row[71] == "https://oss/a.jpg"     # main photo col BS
    assert row[72] == "https://oss/b.jpg"     # photo 1 col BT


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #
def test_prepare_accepts_valid_items(memory_session, tmp_path):
    batch = _seed_batch(memory_session, tmp_path, n=3, status=ItemStatus.QUEUED)
    rep = svc.run_prepare(memory_session, batch_id=batch.id)
    assert rep["prepared"] == 3
    assert rep["errored"] == 0


def test_full_flow_to_stocked(memory_session, tmp_path):
    batch = _seed_batch(memory_session, tmp_path, n=3, status=ItemStatus.PREPARED)
    omni = FakeOmni(
        {f"SKU-TEST-{i}": f"P{i}" for i in range(3)}
    )

    # images_processed (oss already on the row)
    r = svc.run_images(memory_session, batch_id=batch.id)
    assert r["images_processed"] == 3

    # template_built
    r = svc.build_templates(memory_session, batch_id=batch.id)
    assert r["template_built"] == 3

    # external Excel upload bookkeeping
    r = svc.mark_uploaded(memory_session, batch.id, "UPLOAD-999")
    assert r["template_uploaded"] == 3
    assert r["upload_ref"] == "UPLOAD-999"

    # poll mappings -> product_matched
    r = svc.poll_mappings(memory_session, omni, batch_id=batch.id)
    assert r["product_matched"] == 3
    assert r["mapping_pending"] == 0

    # price + stock (REAL fake call, not dry-run)
    r = svc.apply_price_stock(memory_session, omni, batch_id=batch.id, dry_run=False)
    assert r["priced"] == 3
    assert r["stocked"] == 3
    assert r["failed"] == 0

    # one price_update batch of 3 items, 119*1.1*12=1570.80 RUB = 157080 kopecks
    assert len(omni.price_calls) == 1
    pushed = omni.price_calls[0]
    assert {it["offer_id"] for it in pushed} == {f"SKU-TEST-{i}" for i in range(3)}
    assert pushed[0]["price"] == 157080
    assert pushed[0]["old_price"] == 314160
    assert len(omni.stock_calls) == 1

    # rows are terminal-stocked and reconcile is consistent
    summary = svc.reconcile_batch(memory_session, batch)
    assert summary["stocked"] == 3
    assert summary["total_count"] == 3
    assert summary["consistent"] is True


def test_dry_run_does_not_write(memory_session, tmp_path):
    batch = _seed_batch(memory_session, tmp_path, n=2, status=ItemStatus.PRODUCT_MATCHED)
    omni = FakeOmmi = FakeOmni({"SKU-TEST-0": "P0", "SKU-TEST-1": "P1"})
    before = {it.id: it.status for it in batch.items}

    r = svc.apply_price_stock(memory_session, omni, batch_id=batch.id, dry_run=True)
    assert r["would_price"] == 2
    assert r["would_stock"] == 2
    assert r["priced"] == 0
    # no OMNI write happened, states untouched
    assert omni.price_calls == []
    after = {it.id: it.status for it in batch.items}
    assert before == after


def test_unmapped_rows_stay_pending(memory_session, tmp_path):
    batch = _seed_batch(memory_session, tmp_path, n=2, status=ItemStatus.TEMPLATE_UPLOADED)
    omni = FakeOmni({"SKU-TEST-0": "P0"})  # only half mapped
    r = svc.poll_mappings(memory_session, omni, batch_id=batch.id)
    assert r["product_matched"] == 1
    assert r["mapping_pending"] == 1


def test_deprecated_functions_raise(memory_session, tmp_path):
    with pytest.raises(NotImplementedError):
        svc.run_submit(memory_session, None)
    with pytest.raises(NotImplementedError):
        svc.poll_moderation(memory_session, None)


def test_pull_ozon_products_creates_queued_rows(memory_session, tmp_path):
    png = _make_3x4_png(tmp_path, "ozon_img.png")
    ozon = FakeOzon(
        [
            {
                "id": 555,
                "offer_id": "OZ-1",
                "name": "Ozon mat",
                "price": "99.00",
                "images": [png],
                "attributes": [
                    {"id": 9111, "values": [{"value": "Acme"}]},
                    {"id": 8888, "values": [{"value": "4607012345678"}]},
                ],
            }
        ]
    )
    batch = svc.pull_ozon_products(memory_session, ozon, limit=1, note="unit")
    assert batch.total_count == 1
    item = batch.items[0]
    assert item.offer_id == "OZ-1"
    assert item.status == ItemStatus.QUEUED
