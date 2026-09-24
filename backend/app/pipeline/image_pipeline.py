"""Image normalisation (3:4) + OSS mirroring for the M.Video import (v0.3).

Reuses the SKU00259-proven recipe (scripts/stepA_process_images.py): white-pad
source images onto a 900x1200 (3:4) canvas — no cropping — then upload the
resulting JPEGs to OSS and keep the public URLs for the Excel template.

Two functions, both dependency-injected so the migration unit tests can run
end-to-end without touching the network:

  process_local_images(src_paths, out_dir) -> list[str]   (PIL only)
  upload_processed_to_oss(uploader, local_paths, key_prefix) -> list[dict]

``uploader`` is any object with ``upload_image_file(path, key) -> url``
(see app.oss_uploader.OssUploader).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterable

from PIL import Image

log = logging.getLogger("mvideo.images")

TARGET_W, TARGET_H = 900, 1200  # 3:4
RATIO = 3.0 / 4.0
_EPS = 0.02


def safe_name(offer_id: str) -> str:
    """Filesystem-safe slug for an offer_id (Cyrillic kept)."""
    return re.sub(r"[^0-9A-Za-zА-Яа-яёЁ\-_]+", "_", str(offer_id or "item"))


def _to_3x4(src_path: str, dst_path: str) -> tuple[int, int]:
    """White-pad one image onto the 900x1200 canvas; return (src_w, src_h)."""
    im = Image.open(src_path)
    src_w, src_h = im.width, im.height
    im = im.convert("RGB")
    scale = min(TARGET_W / im.width, TARGET_H / im.height)
    new_w = max(1, round(im.width * scale))
    new_h = max(1, round(im.height * scale))
    if (new_w, new_h) != (im.width, im.height):
        im = im.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (255, 255, 255))
    canvas.paste(im, ((TARGET_W - new_w) // 2, (TARGET_H - new_h) // 2))
    canvas.save(dst_path, format="JPEG", quality=92, optimize=True)
    return src_w, src_h


def process_local_images(
    src_paths: Iterable[str],
    out_dir: str,
    *,
    offer_id: str = "",
) -> list[str]:
    """Resize/white-pad each local source image into ``out_dir``.

    Files are written as ``NN.jpg`` (1-based). Returns the list of produced
    local paths in order. ``out_dir`` is created if missing.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_paths: list[str] = []
    slug = safe_name(offer_id) or "item"
    for idx, src in enumerate(list(src_paths), start=1):
        if not src or not os.path.exists(src):
            log.warning("image missing, skipped: %s", src)
            continue
        dst = os.path.join(out_dir, f"{slug}-{idx:02d}.jpg")
        try:
            _to_3x4(src, dst)
        except Exception as exc:  # noqa: BLE001 - one bad image must not kill batch
            log.warning("image process failed %s: %s", src, exc)
            continue
        out_paths.append(dst)
    return out_paths


def upload_processed_to_oss(
    uploader: Any,
    local_paths: Iterable[str],
    key_prefix: str,
) -> list[dict]:
    """Upload processed local images; return [{idx, url, key}] (OSS manifest).

    ``uploader`` needs ``upload_image_file(path, key) -> url``. Only the public
    URL is returned/logged; credentials stay inside the uploader.
    """
    manifest: list[dict] = []
    prefix = key_prefix.strip("/")
    for idx, path in enumerate(list(local_paths), start=1):
        key = f"{prefix}/{idx:02d}.jpg"
        try:
            url = uploader.upload_image_file(path, key)
        except Exception as exc:  # noqa: BLE001
            log.warning("oss upload failed %s: %s", path, exc)
            continue
        manifest.append({"idx": idx, "url": url, "key": key})
    return manifest
