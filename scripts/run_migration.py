"""One-shot CLI migration: Ozon -> M.Video (v0.3 OMNI + Excel-template).

Builds OzonSourceClient + OmniClient from .env and runs the SAFE portion of
the v0.3 pipeline: pull -> prepare -> images -> template_built -> reconcile.

Examples:
  smoke test, first product only (no external writes):
      .venv\\Scripts\\python.exe scripts\\run_migration.py --limit 1
  with the (not-yet-automated) Excel upload hook enabled:
      .venv\\Scripts\\python.exe scripts\\run_migration.py --limit 5 --do-upload

Safety:
  * --do-upload defaults to False; it only logs the upload TODO (no real POST).
  * price/stock are NEVER pushed from here; poll_mappings is read-only and the
    price/stock stage runs dry-run (it only prints how many rows WOULD be
    pushed). No real price/stock change.
"""

import argparse
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.integrations.omni_client import OmniClient  # noqa: E402
from app.integrations.ozon_client import OzonSourceClient  # noqa: E402
from app.ratelimit import RequestBudgeter  # noqa: E402
from app.pipeline.migrate_service import run_once  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Ozon -> M.Video one-shot migration (v0.3 OMNI)")
    ap.add_argument("--limit", type=int, default=None, help="only pull the first N products (smoke)")
    ap.add_argument("--note", default="", help="free-text note on the batch")
    ap.add_argument(
        "--do-upload",
        action="store_true",
        default=False,
        help="enable the Excel upload hook (currently a TODO log only; no real POST)",
    )
    args = ap.parse_args()

    st = get_settings()
    if not st.ozon_client_id or not st.ozon_api_key:
        print("ERROR: OZON_CLIENT_ID / OZON_API_KEY missing in .env")
        return 1
    if not (st.omni_api_key or st.mvideo_api_key):
        print("ERROR: OMNI_API_KEY missing in .env (create it in ЛК -> Доступ к API with Omniom permissions)")
        return 1

    init_db()
    session = SessionLocal()
    budgeter = RequestBudgeter(session)

    ozon = OzonSourceClient(
        client_id=st.ozon_client_id,
        api_key=st.ozon_api_key,
        base_url=st.ozon_api_base_url,
        timeout_seconds=st.ozon_timeout_seconds,
    )
    omni = OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
        budgeter=budgeter,
    )
    try:
        summary = run_once(
            session, ozon, omni,
            limit=args.limit, note=args.note, do_upload=args.do_upload,
        )
    finally:
        ozon.close()
        omni.close()
        session.close()

    print("\n=== migration summary (v0.3, safe/dry-run) ===")
    for k, v in summary.items():
        if k == "by_status":
            continue
        print(f"  {k}: {v}")
    print("  by_status:")
    for st_name, cnt in (summary.get("by_status") or {}).items():
        print(f"    - {st_name}: {cnt}")
    print("\nNote: no real price/stock write was made; Excel upload is manual.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
