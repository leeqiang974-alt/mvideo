# -*- coding: utf-8 -*-
"""Re-read SKU00259 prices via OMNI to check whether the push took effect."""
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
    with OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
    ) as client:
        pi = client.price_info({"offer_id": OFFERS}, limit=100)
        for p in (pi.get("prices") or []):
            rub = p["price"] / 100.0
            print(f"{p['offer_id']} | price_kopek={p['price']} (={rub:.2f} RUB) | vat={p.get('vat')} | old={p.get('old_price')}")
        print("total:", len(pi.get("prices") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
