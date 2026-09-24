# -*- coding: utf-8 -*-
"""Real-write push for SKU00259 family (8 variants) with v0.6.3 rules:
   sell = Ozon CNY * 1.1 * MV_RUB_RATE -> kopecks; old_price = 2 * sell; stock = 999.
   Uses OMNI API directly (live keys from .env). No secrets printed.
"""
import os, sys, logging
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if not os.path.isdir(_BACKEND):
    _BACKEND = r"C:\MvideoERP\backend"
sys.path.insert(0, _BACKEND)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.integrations.omni_client import OmniClient
from app.ratelimit import RequestBudgeter
from app.currency import build_price_item, build_stock_item

# SKU00259 family: (offer_id, ozon CNY price, mv_product_id)
VARIANT_PRICING = [
    ("SKU00259",            "119.00", "403159211"),
    ("SKU00259-yellow",     "119.90", "403159210"),
    ("SKU00259-lyellow",    "119.90", "403159212"),
    ("SKU00259-lyellow-hi", "119.90", "403159213"),
    ("SKU00259-blue-hi",    "119.90", "403159214"),
    ("SKU00259-white-hi",   "119.90", "403159215"),
    ("SKU00259-orange-hi",  "119.90", "403159216"),
    ("SKU00259-green-hi",   "119.90", "403159217"),
]
LOCATION_ID = "10011496"

def main() -> int:
    st = get_settings()
    if not (st.omni_api_key or st.mvideo_api_key):
        print("ERROR: no OMNI_API_KEY in .env")
        return 1
    init_db()
    session = SessionLocal()
    budgeter = RequestBudgeter(session)
    omni = OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
        budgeter=budgeter,
    )
    try:
        price_items = [build_price_item(o, c, product_id=p) for o, c, p in VARIANT_PRICING]
        stock_items = [build_stock_item(o, product_id=p, location_id=LOCATION_ID) for o, _, p in VARIANT_PRICING]
        print("== PRICE ITEMS (v0.6.3) ==")
        for it in price_items:
            print(f"  {it['product_id']} price={it['price']} kop ({it['price']/100:.2f} RUB) old={it['old_price']} kop ({it['old_price']/100:.2f} RUB)")
        print("== STOCK ITEMS (fixed 999) ==")
        for it in stock_items:
            print(f"  {it['product_id']} count={it['count']} location={it.get('location_id')}")

        print("\n>> price_update ...")
        pr = omni.price_update(price_items)
        print("   price_update resp:", pr)
        print(">> stock_update ...")
        sr = omni.stock_update(stock_items)
        print("   stock_update resp:", sr)

        # readback (async; wait ~60s before trusting readback)
        print("\n== READBACK (price/info + stock/info) ==")
        import time
        time.sleep(60)
        mp = omni.mapping_list()  # returns mapping dict
        # price info
        pinfo = omni._post("price.info", {"filter": {"product_ids": [p for _, _, p in VARIANT_PRICING]}})
        sinfo = omni._post("stock.info", {"filter": {"product_ids": [p for _, _, p in VARIANT_PRICING]}})
        print("price.info:", pinfo)
        print("stock.info:", sinfo)
    finally:
        omni.close()
        session.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
