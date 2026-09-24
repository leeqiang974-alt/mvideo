# -*- coding: utf-8 -*-
"""用 Ozon API 重新拉取 sellersku0002 的属性（UTF-8 解码），确认切带机形态。"""
import os, sys, json
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if not os.path.isdir(_BACKEND):
    _BACKEND = r"C:\MvideoERP\backend"
sys.path.insert(0, _BACKEND)

from app.config import get_settings
from app.integrations.ozon_client import OzonSourceClient

def fix(s):
    """Ozon 返回的俄文被错误编码，尝试修复。"""
    if not s: return s
    try:
        return s.encode("latin-1").decode("utf-8", errors="replace")
    except Exception:
        return s

def main() -> int:
    st = get_settings()
    oz = OzonSourceClient(
        client_id=st.ozon_client_id,
        api_key=st.ozon_api_key,
        base_url=st.ozon_api_base_url,
        timeout_seconds=30,
    )
    out_lines = []
    try:
        # 直接用 v3 商品列表查 offer_id
        raw = oz._post("/v3/product/list", {"filter": {"offer_id": ["sellersku0002"], "visibility": "ALL"}, "limit": 10})
        items = (raw.get("result") or {}).get("items") or []
        out_lines.append("ITEMS: %d" % len(items))
        for it in items:
            pid = it.get("product_id")
            out_lines.append("  product_id: %s offer_id: %s" % (pid, fix(it.get("offer_id"))))
            attrs = oz.get_product_attributes([pid])
            for r in (attrs.get("result") or []):
                out_lines.append("  === attributes for %s ===" % fix(r.get("offer_id")))
                for a in (r.get("attributes") or []):
                    vals = [v.get("value") for v in (a.get("values") or [])]
                    out_lines.append("   id=%s name=%s = %s" % (a.get("attribute_id"), fix(a.get("name")), [fix(v) for v in vals][:4]))
    finally:
        oz.close()
    with open(r"C:\MvideoERP\_sku002_attrs_out.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("written", len(out_lines), "lines")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
