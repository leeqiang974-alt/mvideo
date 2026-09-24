# -*- coding: utf-8 -*-
"""Step B: upload processed 3:4 images to Aliyun OSS bucket ozonshanghai.

Object keys: mvideo/sku00259/<safe_offer>/NN.jpg
Never prints AK/SK. Writes work/oss_urls_manifest.json with public URLs.
"""
import json
import sys
from pathlib import Path

import oss2

ROOT = Path(r"E:\mvideo\MvideoERP")
MANIFEST_IN = ROOT / "work" / "processed_manifest.json"
MANIFEST_OUT = ROOT / "work" / "oss_urls_manifest.json"
CRED_FILE = Path(r"D:\Desktop\api\阿里云的key和secret.txt")
ENDPOINT = "oss-cn-shanghai.aliyuncs.com"
BUCKET = "ozonshanghai"
PREFIX = "mvideo/sku00259"


def load_creds():
    lines = [x.strip() for x in CRED_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(lines) < 4:
        raise RuntimeError("credential file malformed")
    return lines[1], lines[3]


def main() -> int:
    ak, sk = load_creds()
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, f"https://{ENDPOINT}", BUCKET, connect_timeout=15)

    data = json.loads(MANIFEST_IN.read_text(encoding="utf-8"))
    result = []
    uploaded = 0
    for variant in data:
        offer = variant["offer_id"]
        # build safe key folder from offer_id
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in offer)
        urls = []
        for img in variant["images"]:
            local = Path(img["local_path"])
            obj_key = f"{PREFIX}/{safe}/{img['idx']:02d}.jpg"
            bucket.put_object_from_file(obj_key, str(local), headers={"Content-Type": "image/jpeg"})
            meta = bucket.head_object(obj_key)
            if meta.status != 200:
                raise RuntimeError(f"HEAD verify failed: {obj_key}")
            url = f"https://{BUCKET}.{ENDPOINT}/{obj_key}"
            urls.append({"idx": img["idx"], "url": url, "key": obj_key})
            uploaded += 1
            print(f"  OK {offer} #{img['idx']:02d} -> {url}")
        result.append(
            {
                "offer_id": offer,
                "sku_id": variant["sku_id"],
                "price": variant["price"],
                "old_price": variant["old_price"],
                "currency": variant["currency"],
                "images": urls,
            }
        )

    MANIFEST_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE. uploaded={uploaded} -> {MANIFEST_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
