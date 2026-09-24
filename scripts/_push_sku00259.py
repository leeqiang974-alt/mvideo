"""REAL-WRITE verification: push SKU00259 (8 variants) price+stock to M.Video via OMNI.

v0.3.2 - verifies the OMNI write channel end to end. Reads settings from .env
(OMNI_API_KEY), converts CNY->RUB (MV_RUB_RATE default 12.0) -> kopecks, and
calls /v1/product/price/update + /v1/product/stock/update, then reads back
with price/info + stock/info to confirm.

Secrets never leave the laptop and never get printed.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import get_settings  # noqa: E402
from app.currency import build_price_item, build_stock_item  # noqa: E402
from app.integrations.omni_client import OmniClient  # noqa: E402

# offer_id -> (CNY price, FBS stock, OMNI product_id, location_id)
VARIANTS = [
    ("SKU00259", "119.00", 354, "403159211", "10011496"),
    ("SKU00259-Светло-жёлтый", "119.90", 443, "403159212", "10011496"),
    ("SKU00259-Светло-жёлтый-hi", "119.00", 448, "403159213", "10011496"),
    ("SKU00259-Синий-hello", "119.90", 360, "403159214", "10011496"),
    ("SKU00259-Белый-hi", "119.90", 441, "403159215", "10011496"),
    ("SKU00259-оранжевый-hello", "119.90", 410, "403159216", "10011496"),
    ("SKU00259-Зелёный-hello", "119.90", 403, "403159217", "10011496"),
    ("SKU00259-Жёлтый смайлик", "119.00", 443, "403159210", "10011496"),
]

DRY = os.getenv("PUSH_DRY", "1") == "1"


def main() -> int:
    st = get_settings()
    if not (st.omni_api_key or st.mvideo_api_key):
        print("ERROR: no OMNI key in .env")
        return 1
    print(f"rate: {st.mv_rub_rate}  dry_run: {DRY}")

    with OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
    ) as client:
        price_items = [
            build_price_item(offer, cny, product_id=pid, rate=st.mv_rub_rate)
            for offer, cny, _, pid, _ in VARIANTS
        ]
        stock_items = [
            build_stock_item(offer, qty, product_id=pid, location_id=loc)
            for offer, _, qty, pid, loc in VARIANTS
        ]
        print("price items (kopecks):", [(i["product_id"], i["price"]) for i in price_items])
        print("stock items:", [(i["product_id"], i["count"], i.get("location_id")) for i in stock_items])

        if DRY:
            print("DRY-RUN: nothing written. Set PUSH_DRY=0 to actually write.")
            return 0

        pr = client.price_update(price_items, currency="RUB")
        print("price_update failed:", (pr or {}).get("failed"))
        sr = client.stock_update(stock_items)
        print("stock_update failed:", (sr or {}).get("failed"))

        # read back
        offers = [o for o, _, _, _, _ in VARIANTS]
        pi = client.price_info({"offer_id": offers}, limit=100)
        print("readback prices:", [(p["offer_id"], p["price"], p.get("vat")) for p in (pi.get("prices") or [])])
        si = client.stock_info({"offer_id": offers}, limit=100)
        print("readback stocks:", [(s["offer_id"], s["location_id"], s["count"]) for s in (si.get("stocks") or [])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
