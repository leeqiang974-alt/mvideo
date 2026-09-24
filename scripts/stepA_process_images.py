# -*- coding: utf-8 -*-
"""Step A: download all SKU00259 variant images and normalize to 3:4 vertical.

Strategy (user-chosen): white-pad (no cropping). Target canvas 900x1200 (3:4).
Images already 3:4 are re-encoded at max quality without padding.
Output: work/sku00259_processed/<offer_id_safe>/N.jpg  +  processed_manifest.json
"""
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(r"E:\mvideo\MvideoERP")
JSON_PATH = ROOT / "sku00259_full.json"
OUT_DIR = ROOT / "work" / "sku00259_processed"
MANIFEST = ROOT / "work" / "processed_manifest.json"

TARGET_W, TARGET_H = 900, 1200  # 3:4
RATIO = 3.0 / 4.0
EPS = 0.02  # tolerance for "already 3:4"


def safe_name(offer_id: str) -> str:
    return re.sub(r"[^0-9A-Za-zА-Яа-яёЁ\-_]+", "_", offer_id)


def is_3x4(im: Image.Image) -> bool:
    r = im.width / im.height
    return abs(r - RATIO) < EPS


def to_3x4(img_bytes: bytes) -> bytes:
    """Take JPEG bytes, return JPEG bytes on 900x1203 canvas, white-padded."""
    im = Image.open(io.BytesIO(img_bytes))
    im = im.convert("RGB")
    # Scale to fit target box preserving aspect ratio.
    scale = min(TARGET_W / im.width, TARGET_H / im.height)
    new_w = max(1, round(im.width * scale))
    new_h = max(1, round(im.height * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (255, 255, 255))
    off_x = (TARGET_W - new_w) // 2
    off_y = (TARGET_H - new_h) // 2
    canvas.paste(im, (off_x, off_y))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> int:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    items = data["product_info"]["items"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    total_in = total_out = 0
    for it in items:
        offer = it["offer_id"]
        sdir = OUT_DIR / safe_name(offer)
        sdir.mkdir(parents=True, exist_ok=True)
        urls = it.get("images", [])
        out_urls_local = []
        for idx, u in enumerate(urls, start=1):
            total_in += 1
            raw = fetch(u)
            before = Image.open(io.BytesIO(raw))
            bw, bh = before.width, before.height
            out_bytes = to_3x4(raw)
            out_path = sdir / f"{idx:02d}.jpg"
            out_path.write_bytes(out_bytes)
            total_out += 1
            out_urls_local.append(
                {
                    "idx": idx,
                    "src_url": u,
                    "src_size": [bw, bh],
                    "src_was_3x4": is_3x4(before),
                    "local_path": str(out_path),
                    "local_bytes": len(out_bytes),
                }
            )
            print(f"  [{offer}] {idx}/{len(urls)} {bw}x{bh} -> 900x1200  ({len(out_bytes)//1024} KB)")
        manifest.append(
            {
                "offer_id": offer,
                "sku_id": it["id"],
                "price": it["price"],
                "old_price": it.get("old_price"),
                "currency": it.get("currency_code", "CNY"),
                "images": out_urls_local,
            }
        )

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE. input={total_in} output={total_out} -> {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
