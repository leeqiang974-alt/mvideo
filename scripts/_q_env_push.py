# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")))
from app.config import get_settings
st = get_settings()
print("omni_api_key set:", bool(st.omni_api_key), "len:", len(st.omni_api_key or ""))
print("omni_api_base_url:", st.omni_api_base_url)
print("mv_rub_rate:", st.mv_rub_rate)
print("mv_apply_writes:", getattr(st, "mv_apply_writes", None))
print("omni_timeout:", st.omni_timeout_seconds)
