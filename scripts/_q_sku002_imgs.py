# -*- coding: utf-8 -*-
"""拉取 sellersku0002 (ozon 1237743084) 的图片 URL 并写到本地 json。"""
import os, sys, json
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if not os.path.isdir(_BACKEND):
    _BACKEND = r"C:\MvideoERP\backend"
sys.path.insert(0, _BACKEND)

from app.config import get_settings
from app.integrations.ozon_client import OzonSourceClient

OUT = r"C:\MvideoERP\_sku002_imgs.json"

def main() -> int:
    st = get_settings()
    oz = OzonSourceClient(
        client_id=st.ozon_client_id,
        api_key=st.ozon_api_key,
        base_url=st.ozon_api_base_url,
        timeout_seconds=30,
    )
    try:
        attrs = oz.get_product_attributes([1237743084])
        results = attrs.get("result") or []
        out = []
        for r in results:
            out.append({
                "product_id": r.get("product_id"),
                "offer_id": r.get("offer_id"),
                "images": r.get("images") or [],
                "primary_image": r.get("primary_image") or "",
            })
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        n = len(out[0]["images"]) if out else 0
        p = out[0].get("primary_image") if out else ""
        print("written", OUT, "images:", n, "primary:", p[:80])
    finally:
        oz.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
