# -*- coding: utf-8 -*-
"""Readback SKU00259 family price/stock after v0.6.3 push (no empty-filter calls)."""
import os, sys, json
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if not os.path.isdir(_BACKEND):
    _BACKEND = r"C:\MvideoERP\backend"
sys.path.insert(0, _BACKEND)

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.integrations.omni_client import OmniClient
from app.ratelimit import RequestBudgeter

PIDS = ["403159211","403159210","403159212","403159213","403159214","403159215","403159216","403159217"]

def main() -> int:
    st = get_settings()
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
        pinfo = omni.price_info({"product_id": PIDS}, limit=100)
        print("PRICE.INFO:", json.dumps(pinfo, ensure_ascii=False))
        sinfo = omni.stock_info({"product_id": PIDS}, limit=100)
        print("STOCK.INFO:", json.dumps(sinfo, ensure_ascii=False))
    finally:
        omni.close()
        session.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
