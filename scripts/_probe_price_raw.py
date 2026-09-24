# -*- coding: utf-8 -*-
"""Raw response probe: push ONE price, dump the full raw response body."""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import get_settings  # noqa: E402
from app.currency import build_price_item  # noqa: E402
from app.integrations.omni_client import OmniClient  # noqa: E402


def main() -> int:
    st = get_settings()
    item = build_price_item("SKU00259", "119.00", product_id="403159211", rate=st.mv_rub_rate)
    print("item:", json.dumps(item, ensure_ascii=False))

    # Use raw httpx through the same client to see the FULL response
    with OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
    ) as client:
        resp = client._http.post("/v1/product/price/update", json={"items": [item], "currency": "RUB"})
        print("status:", resp.status_code)
        print("headers:", dict(resp.headers))
        print("body:", resp.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
