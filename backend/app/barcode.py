"""Barcode rules for M.Video (Маркетплейс) cards.

v0.1 (2026-09-17):
- Marketplace-type cards use EAN18 (18 digits).
- Input validation per seller docs: only digits or Latin letters,
  length 6..13.  Whitespace is stripped, letters are uppercased.
- EAN13 (13 digits) auto-converts to EAN18 = original 13 chars + 5-digit
  supplier/vendor id (padded with leading zeros to exactly 5 digits).

Pure functions, no IO, fully offline-testable.
"""

from __future__ import annotations

_ALLOWED_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_INPUT_MIN_LEN = 6
_INPUT_MAX_LEN = 13
_EAN13_LEN = 13
_EAN18_LEN = 18
_VENDOR_ID_LEN = 5


def normalize_barcode(raw: str) -> str:
    """Strip all whitespace and uppercase letters. No length/charset check.

    ``barcode_valid_for_input`` is the gate that decides acceptance.
    """
    if raw is None:
        return ""
    # remove every whitespace char (spaces, tabs, newlines)
    return "".join(str(raw).split()).upper()


def barcode_valid_for_input(raw: str) -> bool:
    """True iff the raw barcode is acceptable as M.Video input.

    Rules (seller docs): only digits or Latin letters; 6..13 chars after
    whitespace removal and uppercasing.
    """
    norm = normalize_barcode(raw)
    if not (_INPUT_MIN_LEN <= len(norm) <= _INPUT_MAX_LEN):
        return False
    return all(ch in _ALLOWED_CHARS for ch in norm)


def to_ean18(barcode13: str, vendor_id: str) -> str:
    """Convert a 13-char (EAN13) barcode to EAN18.

    EAN18 = original 13 chars + 5-digit vendor id (leading-zero padded).

    Raises ValueError on bad input; callers should pre-validate with
    ``barcode_valid_for_input`` and confirm length == 13.
    """
    bcode = normalize_barcode(barcode13)
    vid = normalize_barcode(vendor_id)
    if len(bcode) != _EAN13_LEN:
        raise ValueError(
            f"barcode must be 13 chars for EAN18 conversion, got {len(bcode)}"
        )
    if not bcode.isdigit():
        raise ValueError("EAN13 part must be digits")
    if not vid.isdigit():
        raise ValueError(f"vendor_id must be digits, got {vid!r}")
    if len(vid) > _VENDOR_ID_LEN:
        raise ValueError(
            f"vendor_id must fit in {_VENDOR_ID_LEN} digits, got {len(vid)}"
        )
    vid5 = vid.zfill(_VENDOR_ID_LEN)
    result = bcode + vid5
    if len(result) != _EAN18_LEN:
        raise AssertionError("EAN18 length mismatch")
    return result
