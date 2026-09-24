"""Tests for quality_gate (v0.2, aligned with verified live OpenAPI)."""

from PIL import Image

from backend.app.quality_gate import run_quality_gate


def _good_image(tmp_path):
    p = tmp_path / "img.png"
    Image.new("RGB", (975, 1300), (255, 255, 255)).save(p, "PNG")
    return str(p)


def _good_item(tmp_path, **over):
    item = {
        "name": "Test Item",
        "brand": "Acme",
        "source_barcode": "4607012345678",
        "mv_group_id": "100",
        "mv_nds": "USN",
        "images": [_good_image(tmp_path)],
        "dimensions": {"length_cm": 13, "width_cm": 6.5, "height_cm": 8, "weight_kg": 0.4},
    }
    item.update(over)
    return item


VENDOR = "42"  # kept for signature compatibility; no longer used for EAN18


class TestHappyPath:
    def test_valid_item_ok(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path), vendor_id=VENDOR, tn_ved_present=True
        )
        assert rep.ok is True, rep.errors
        assert rep.barcode13 == "4607012345678"
        assert rep.errors == []

    def test_ean13_passes_without_vendor(self, tmp_path):
        # vendor_id is not needed anymore: create API takes EAN13 directly
        rep = run_quality_gate(
            _good_item(tmp_path, source_barcode="4607012345678"),
            vendor_id="",
            tn_ved_present=True,
        )
        assert rep.ok is True, rep.errors
        assert rep.barcode13 == "4607012345678"


class TestLockedFields:
    def test_missing_group_id_error(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path, mv_group_id=""),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is False
        assert any("mv_group_id" in e for e in rep.errors)

    def test_missing_name_error(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path, name=""),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is False
        assert any("name" in e for e in rep.errors)

    def test_missing_brand_error(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path, brand=""),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is False
        assert any("brand" in e for e in rep.errors)

    def test_missing_nds_error(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path, mv_nds=""),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is False
        assert any("mv_nds" in e for e in rep.errors)

    def test_tn_ved_absent_warns(self, tmp_path):
        # v0.6: TN VED is a warning (manual registry lookup), not a blocker.
        rep = run_quality_gate(
            _good_item(tmp_path), vendor_id=VENDOR, tn_ved_present=False
        )
        assert rep.ok is True
        assert any("tn_ved" in w.lower() for w in rep.warnings)


class TestBarcode:
    def test_short_barcode_warns(self, tmp_path):
        # v0.6: Excel template auto-generates barcode; non-EAN13 is a warning.
        rep = run_quality_gate(
            _good_item(tmp_path, source_barcode="12345"),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is True
        assert rep.barcode13 == ""
        assert any("генерировать" in w.lower() for w in rep.warnings)

    def test_non_13_digit_warns(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path, source_barcode="1234567"),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is True
        assert any("генерировать" in w.lower() for w in rep.warnings)

    def test_letters_warns(self, tmp_path):
        rep = run_quality_gate(
            _good_item(tmp_path, source_barcode="ABC1234567890"),
            vendor_id=VENDOR,
            tn_ved_present=True,
        )
        assert rep.ok is True
        assert any("генерировать" in w.lower() for w in rep.warnings)


class TestImagesPropagate:
    def test_bad_image_flags_error(self, tmp_path):
        # no images -> "too few"
        item = _good_item(tmp_path, images=[])
        rep = run_quality_gate(item, vendor_id=VENDOR, tn_ved_present=True)
        assert rep.ok is False
        assert rep.report["images"]["count"] == 0
        assert any("too few" in e for e in rep.errors)
