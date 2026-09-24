"""M.Video product image rules.

v0.1 (2026-09-17), per seller docs:
- 1..15 images per card.
- Vertical 3:4 (width:height), optimal 975x1300.
- Resolution band: 200x250 .. 3520x4400.
- <= 10 MB per file.
- Formats: JPEG / JPG / PNG / WebP / BMP.
- Main image: white background, no shadows (not auto-detected here, flagged
  downstream). Screen-category first image must be powered-on screen fill.

Checks a single image (local path or http(s) URL) with Pillow, then a list
with aggregate error/warning semantics. Network reads use httpx and are
only triggered when a URL is passed; tests use local temp PNGs so the whole
suite runs fully offline.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

from PIL import Image

# --- constants (seller docs) -------------------------------------------------
MIN_IMAGES = 1
MAX_IMAGES = 15
MIN_WIDTH = 200
MIN_HEIGHT = 250
MAX_WIDTH = 3520
MAX_HEIGHT = 4400
OPTIMAL_WIDTH = 975
OPTIMAL_HEIGHT = 1300
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
TARGET_RATIO = OPTIMAL_WIDTH / OPTIMAL_HEIGHT  # 0.75
# Tolerance on width/height before we call the ratio "wrong".
# Doc's own band endpoints are 200x250 and 3520x4400 (both 0.8 vs 3:4=0.75),
# so 0.8 must be accepted; a square (1.0) must be rejected.
RATIO_TOLERANCE = 0.06

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class ImageCheck:
    source: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    ratio: float = 0.0
    size_bytes: int = 0
    fmt: str = ""


def _load_image(source: str) -> tuple[Image.Image, bytes, int]:
    """Return (PIL Image, raw bytes, byte count) from a path or http(s) URL."""
    if source.startswith(("http://", "https://")):
        import httpx  # local import: tests never hit network

        resp = httpx.get(source, timeout=30.0)
        resp.raise_for_status()
        data = resp.content
        img = Image.open(io.BytesIO(data))
        return img, data, len(data)

    with open(source, "rb") as fh:
        data = fh.read()
    img = Image.open(io.BytesIO(data))
    return img, data, len(data)


def _ext_of(source: str) -> str:
    return os.path.splitext(source.split("?")[0])[1].lower()


def check_image(source: str) -> ImageCheck:
    """Validate one image against the M.Video rules. Never raises on bad
    media: an unreadable image is recorded as an error."""
    result = ImageCheck(source=source)
    try:
        img, data, nbytes = _load_image(source)
    except Exception as exc:  # noqa: BLE001 - any read error is a card error
        result.ok = False
        result.errors.append(f"cannot read image: {exc}")
        return result

    result.size_bytes = nbytes
    result.fmt = (img.format or "").upper()
    result.width = int(img.size[0])
    result.height = int(img.size[1])
    if result.height:
        result.ratio = result.width / result.height

    # 1) format whitelist
    ext = _ext_of(source)
    if result.fmt not in ALLOWED_FORMATS and ext not in ALLOWED_EXTS:
        result.ok = False
        result.errors.append(
            f"format not allowed: {result.fmt or ext or 'unknown'}"
        )

    # 2) size cap
    if nbytes > MAX_BYTES:
        result.ok = False
        result.errors.append(
            f"file too large: {nbytes} bytes > {MAX_BYTES}"
        )

    # 3) resolution band
    if not (MIN_WIDTH <= result.width <= MAX_WIDTH and
            MIN_HEIGHT <= result.height <= MAX_HEIGHT):
        result.ok = False
        result.errors.append(
            f"resolution out of band: {result.width}x{result.height} "
            f"(allowed {MIN_WIDTH}x{MIN_HEIGHT}..{MAX_WIDTH}x{MAX_HEIGHT})"
        )

    # 4) ratio ~ 3:4
    if result.height:
        dev = abs(result.ratio - TARGET_RATIO)
        if dev > RATIO_TOLERANCE:
            result.ok = False
            result.errors.append(
                f"ratio {result.ratio:.3f} deviates from 3:4 ({TARGET_RATIO:.3f}) "
                f"by {dev:.3f}"
            )
        elif (result.width, result.height) != (OPTIMAL_WIDTH, OPTIMAL_HEIGHT):
            result.warnings.append(
                f"not optimal resolution {result.width}x{result.height} "
                f"(optimal {OPTIMAL_WIDTH}x{OPTIMAL_HEIGHT})"
            )

    return result


def check_image_list(sources: list[str]) -> dict:
    """Aggregate-check a list of image URLs/paths for one card.

    Returns {"ok", "errors", "warnings", "count", "items": [ImageCheck...]}.
    """
    errors: list[str] = []
    warnings: list[str] = []
    items = [check_image(s) for s in (sources or [])]

    count = len(items)
    if count < MIN_IMAGES:
        errors.append(f"too few images: {count} (need >= {MIN_IMAGES})")
    elif count > MAX_IMAGES:
        errors.append(f"too many images: {count} (max {MAX_IMAGES})")

    for it in items:
        errors.extend(it.errors)
        warnings.extend(it.warnings)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "count": count,
        "items": items,
    }
