"""Tests for barcode rules (v0.1)."""

import pytest

from backend.app.barcode import (
    barcode_valid_for_input,
    normalize_barcode,
    to_ean18,
)


class TestNormalize:
    def test_strips_spaces_and_uppercases(self):
        assert normalize_barcode("  123 4567 89012  ") == "123456789012"

    def test_handles_none(self):
        assert normalize_barcode(None) == ""

    def test_keeps_latin_letters(self):
        assert normalize_barcode("abc def") == "ABCDEF"


class TestValidForInput:
    @pytest.mark.parametrize("raw", ["123456", "1234567890123", "ABC123XYZ", "a1b2c3"])
    def test_accepts(self, raw):
        assert barcode_valid_for_input(raw) is True

    @pytest.mark.parametrize("raw", ["", "12345", "12345678901234", "abcd!ef"])
    def test_rejects(self, raw):
        assert barcode_valid_for_input(raw) is False


class TestToEan18:
    def test_converts_padding_vendor_id(self):
        assert to_ean18("4607012345678", "42") == "460701234567800042"

    def test_vendor_id_already_five_digits(self):
        assert to_ean18("4607012345678", "00042") == "460701234567800042"

    def test_length_is_18(self):
        assert len(to_ean18("4607012345678", "1")) == 18

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            to_ean18("123", "42")

    def test_non_digit_vendor_raises(self):
        with pytest.raises(ValueError):
            to_ean18("4607012345678", "AB")

    def test_vendor_too_long_raises(self):
        with pytest.raises(ValueError):
            to_ean18("4607012345678", "123456")
