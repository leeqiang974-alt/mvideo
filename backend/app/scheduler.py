"""Background poller for the v0.3 OMNI pipeline.

v0.3 (2026-09-18): replaced the old «На модерации» poll with an OMNI mapping
poll. Every tick:
  1. poll mappings for TEMPLATE_UPLOADED / MAPPING_PENDING rows
     (OmniClient.iter_mappings -> offer_id resolves to product_id)
  2. apply price+stock for newly PRODUCT_MATCHED rows, DRY-RUN by default
     (set MV_APPLY_WRITES=1 to actually push; off by default so the poller
     never silently changes prices/stock).

No APScheduler dependency. A plain daemon thread loops every
``POLL_INTERVAL_SECONDS``. It never blocks startup and dies with the process.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from app.config import get_settings
from app.database import SessionLocal
from sqlalchemy import select  # noqa: F401  (kept for parity; not used here)

log = logging.getLogger("mvideo.scheduler")

_stop = threading.Event()
_thread: threading.Thread | None = None


def _build_omni_client():
    """Lazily build an OmniClient from settings (imports avoided at load)."""
    from app.integrations.omni_client import OmniClient
    from app.ratelimit import RequestBudgeter

    st = get_settings()
    session = SessionLocal()
    budgeter = RequestBudgeter(session)
    client = OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
        budgeter=budgeter,
    )
    return client, session, budgeter


def _loop_once() -> None:
    from app.pipeline.migrate_service import apply_price_stock, poll_mappings

    st = get_settings()
    if not (st.omni_api_key or st.mvideo_api_key):
        log.warning("OMNI_API_KEY empty; poller idle")
        return
    # Default to dry-run: the poller must not silently push price/stock.
    do_writes = os.getenv("MV_APPLY_WRITES", "0") == "1"
    client = None
    session = None
    try:
        client, session, _ = _build_omni_client()
        poll_mappings(session, client)
        apply_price_stock(session, client, dry_run=not do_writes)
    except Exception as exc:  # noqa: BLE001
        log.exception("poller tick failed: %s", exc)
    finally:
        if client is not None:
            client.close()
        if session is not None:
            session.close()


def _run() -> None:
    st = get_settings()
    log.info("poller started: interval=%ss batch=%s", st.poll_interval_seconds, st.poll_batch_size)
    while not _stop.is_set():
        try:
            _loop_once()
        except Exception as exc:  # noqa: BLE001
            log.exception("poller tick error: %s", exc)
        _stop.wait(timeout=st.poll_interval_seconds)


def start_poller() -> threading.Thread:
    """Start the daemon poller. Idempotent."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return _thread
    _stop.clear()
    _thread = threading.Thread(target=_run, name="mvideo-poller", daemon=True)
    _thread.start()
    return _thread


def stop_poller(timeout: float = 5.0) -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=timeout)
