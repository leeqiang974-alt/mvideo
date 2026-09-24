# -*- coding: utf-8 -*-
"""Download sellersku0002 primary image -> 3:4 white-pad 900x1200 -> upload OSS.

Writes work/oss_urls_dispenser.json (single-entry manifest) for the template.
"""
import json
import sys
from pathlib import Path

import httpx
import oss2
from PIL import Image

ROOT = Path(r"E:\mvideo\MvideoERP")
OUT_MANIFEST = ROOT / "work" / "oss_urls_dispenser.json"
LOCAL_DIR = ROOT / "work" / "sku002_processed"
CRED_FILE = Path(r"D:\Desktop\api\阿里云的key和secret.txt")
ENDPOINT = "oss-cn-shanghai.aliyuncs.com"
BUCKET = "ozonshanghai"
PREFIX = "mvideo/dispenser"

SRC_URL = "https://ir-20.ozone.ru/s3/multimedia-1-8/7171021016.jpg"
OFFER = "sellersku0002"

def load_creds():
    lines = [x.strip() for x in CRED_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(lines) < 4:
        raise RuntimeError("credential file malformed")
    return lines[1], lines[3]

def process_3x4(src_path: Path, out_path: Path):
    """Crop/resize to 3:4 and pad with white to 900x1200, keeping full subject."""
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    target_ratio = 3 / 4
    cur = w / h
    if cur < target_ratio:
        # too tall -> pad width
        nw = int(h * target_ratio)
        canvas = Image.new("RGB", (nw, h), "white")
        canvas.paste(im, ((nw - w) // 2, 0))
        im = canvas
    elif cur > target_ratio:
        # too wide -> pad height
        nh = int(w / target_ratio)
        canvas = Image.new("RGB", (w, nh), "white")
        canvas.paste(im, (0, (nh - h) // 2))
        im = canvas
    im = im.resize((900, 1200), Image.LANCZOS)
    im.save(out_path, "JPEG", quality=92)
    print(f"  processed {out_path.name}: {im.size}")

def main() -> int:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    src = LOCAL_DIR / "src.jpg"
    out = LOCAL_DIR / "00.jpg"

    # download
    r = httpx.get(SRC_URL, timeout=30, follow_redirects=True)
    r.raise_for_status()
    src.write_bytes(r.content)
    print(f"downloaded {len(r.content)} bytes")

    # process
    process_3x4(src, out)

    # upload
    ak, sk = load_creds()
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, f"https://{ENDPOINT}", BUCKET, connect_timeout=15)
    obj_key = f"{PREFIX}/{OFFER}/00.jpg"
    bucket.put_object_from_file(obj_key, str(out), headers={"Content-Type": "image/jpeg"})
    meta = bucket.head_object(obj_key)
    if meta.status != 200:
        raise RuntimeError(f"HEAD verify failed: {obj_key}")
    url = f"https://{BUCKET}.{ENDPOINT}/{obj_key}"

    manifest = [
        {
            "offer_id": OFFER,
            "price": "67.20",
            "old_price": "",
            "currency": "CNY",
            "images": [{"idx": 0, "url": url, "key": obj_key}],
        }
    ]
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print(f"uploaded {url}")
    print(f"manifest -> {OUT_MANIFEST}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
