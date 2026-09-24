"""Check that required env vars are present.

Prints ONLY which keys are missing/empty - never the values themselves.
Run: .venv\\Scripts\\python.exe scripts\\check_env.py
Exit code 0 = all present, 1 = something missing.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import get_settings  # noqa: E402

REQUIRED = [
    ("OMNI_API_KEY", "M.Video OMNI API key (ЛК -> Доступ к API, Omniom permissions)"),
    ("OZON_CLIENT_ID", "Ozon Seller Client-Id"),
    ("OZON_API_KEY", "Ozon Seller Api-Key"),
]


def main() -> int:
    st = get_settings()
    missing = []
    for key, desc in REQUIRED:
        val = getattr(st, {
            "OMNI_API_KEY": "omni_api_key",
            "OZON_CLIENT_ID": "ozon_client_id",
            "OZON_API_KEY": "ozon_api_key",
        }[key], "")
        if not str(val or "").strip():
            missing.append((key, desc))

    print("check_env:")
    if missing:
        print("  MISSING / EMPTY:")
        for key, desc in missing:
            print(f"    - {key:<20} ({desc})")
        print("  -> copy .env.example to .env and fill the blanks.")
        return 1
    print("  all required keys are present (values hidden).")
    print(f"  DATABASE_URL = {st.database_url}")
    print(f"  OMNI  base   = {st.omni_api_base_url}")
    print(f"  OZON   base  = {st.ozon_api_base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
