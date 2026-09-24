# -*- coding: utf-8 -*-
"""查询 Ozon 类目 17029021 的名称与切带机商品的完整属性（判断真实品类）。"""
import os, sys, json
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if not os.path.isdir(_BACKEND):
    _BACKEND = r"C:\MvideoERP\backend"
sys.path.insert(0, _BACKEND)

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.integrations.ozon_client import OzonSourceClient
from app.ratelimit import RequestBudgeter

def main() -> int:
    st = get_settings()
    init_db()
    oz = OzonSourceClient(
        client_id=st.ozon_client_id,
        api_key=st.ozon_api_key,
        base_url=st.ozon_api_base_url,
        timeout_seconds=30,
    )
    try:
        # 1) 类目树查 17029021 路径
        tree = oz._post("/v1/description-category/tree", {})
        def find(nodes, path=""):
            for n in nodes or []:
                p = path + "/" + n.get("category_name", "")
                if n.get("description_category_id") == 17029021 or n.get("category_id") == 17029021:
                    return p, n
                r = find(n.get("children", []), p)
                if r: return r
            return None
        res = find(tree.get("result", []))
        print("CAT_TREE:", res if res else "not found in tree, keys sample:", (tree.get('result') or [{}])[0].keys() if tree.get('result') else None)
    finally:
        oz.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
