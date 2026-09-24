"""Live OMNI verification via the ERP's own code path (v0.3.1).

Run on the laptop: .venv\\Scripts\\python.exe scripts\\_omni_live_check.py
Prints ONLY non-secret summaries; never prints the api key.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import get_settings  # noqa: E402
from app.integrations.omni_client import OmniClient  # noqa: E402

OFFERS = [
    "SKU00259",
    "SKU00259-Светло-жёлтый",
    "SKU00259-Светло-жёлтый-hi",
    "SKU00259-Синий-hello",
    "SKU00259-Белый-hi",
    "SKU00259-оранжевый-hello",
    "SKU00259-Зелёный-hello",
    "SKU00259-Жёлтый смайлик",
]


def main() -> int:
    st = get_settings()
    key_src = "OMNI_API_KEY" if st.omni_api_key else "MVIDEO_API_KEY(fallback)"
    print(f"using key from: {key_src} (base={st.omni_api_base_url})")
    if not st.omni_api_key and not st.mvideo_api_key:
        print("ERROR: no OMNI key configured")
        return 1

    with OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
    ) as client:
        print("check_connection:", client.check_connection())

        # mapping for the 8 SKU00259 variants
        mappings = client.mapping_list({"offer_id": OFFERS}, limit=100)
        ms = mappings.get("mappings") or []
        print(f"mappings: {len(ms)}")
        for m in ms:
            print(f"  {m['offer_id']} -> {m['product_id']} archived={m.get('is_archived')}")

        # prices
        prices = client.price_info({"offer_id": OFFERS}, limit=100)
        ps = prices.get("prices") or []
        print(f"prices: {len(ps)}")
        for p in ps[:3]:
            print(f"  {p['offer_id']} price_kopek={p['price']} vat={p.get('vat')}")

        # stocks
        stocks = client.stock_info({"offer_id": OFFERS}, limit=100)
        ss = stocks.get("stocks") or []
        print(f"stocks: {len(ss)}")
        for s in ss[:3]:
            print(f"  {s['offer_id']} loc={s['location_id']} count={s['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
