"""FastAPI entrypoint for the M.Video ERP — v0.3 (OMNI + Excel-template).

Routes:
  GET  /health                 local DB reachable, tables present, latest batch
  GET  /health/integrations/omni
                               explicit OMNI api-key connectivity probe
  GET  /api/batches            list recent migration batches
  POST /api/batches            pull N products from Ozon into a new batch
  GET  /api/batches/{id}       one batch + its status summary
  POST /api/batches/{id}/run   advance a batch: prepare/images/templates/
                               poll-mappings/apply price+stock (DRY-RUN)

The background OMNI mapping poller starts as a daemon thread on startup.
Secrets are never returned by any route.
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import MigrationBatch, MigrationItem
from app.pipeline.migrate_service import (
    apply_price_stock,
    build_templates,
    poll_mappings,
    pull_ozon_products,
    run_images,
    run_prepare,
)
from app.pipeline.order_service import list_fbs_orders, summarize_orders
from app.pipeline.reconcile import reconcile_batch
from app.pipeline.report_service import batch_report

log = logging.getLogger("mvideo.api")

app = FastAPI(title="MvideoERP", version="0.4")


@app.on_event("startup")
def _startup() -> None:
    try:
        from app.scheduler import start_poller

        start_poller()
    except Exception as exc:  # noqa: BLE001 - poller is optional
        log.warning("poller not started: %s", exc)


class CreateBatchRequest(BaseModel):
    limit: int | None = None
    note: str = ""


def _batch_summary(b: MigrationBatch) -> dict:
    return {
        "id": b.id,
        "batch_ref": b.batch_ref,
        "status": b.status,
        "total_count": b.total_count,
        "submitted_count": b.submitted_count,
        "on_moderation_count": b.on_moderation_count,
        "ready_count": b.ready_count,
        "priced_count": b.priced_count,
        "stocked_count": b.stocked_count,
        "errored_count": b.errored_count,
        "failed_count": b.failed_count,
        "skipped_count": b.skipped_count,
        "note": b.note,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    tables = sorted(sa_inspect(db.get_bind()).get_table_names())
    latest = db.execute(
        select(MigrationBatch).order_by(MigrationBatch.id.desc()).limit(1)
    ).scalar_one_or_none()

    return {
        "ok": True,
        "app": "MvideoERP",
        "version": "0.4",
        "tables_present": tables,
        "table_count": len(tables),
        "omni_ok": None,
        "omni_status": "not_checked",
        "latest_batch": _batch_summary(latest) if latest else None,
    }


@app.get("/health/integrations/omni")
def omni_health() -> dict:
    """Run the optional external OMNI probe without blocking base liveness."""
    st = get_settings()
    api_key = st.omni_api_key or st.mvideo_api_key
    if not api_key:
        return {"ok": True, "omni_ok": None, "status": "not_configured"}

    try:
        from app.integrations.omni_client import OmniClient

        client = OmniClient(
            api_key=api_key,
            base_url=st.omni_api_base_url,
            timeout_seconds=st.omni_timeout_seconds,
        )
        try:
            omni_ok = client.check_connection()
        finally:
            client.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("omni health check failed: %s", exc)
        omni_ok = False

    return {
        "ok": omni_ok,
        "omni_ok": omni_ok,
        "status": "connected" if omni_ok else "unavailable",
    }


@app.get("/api/batches")
def list_batches(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(MigrationBatch).order_by(MigrationBatch.id.desc()).limit(limit)
    ).scalars().all()
    return {"batches": [_batch_summary(b) for b in rows]}


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)) -> dict:
    b = db.get(MigrationBatch, batch_id)
    if b is None:
        raise HTTPException(404, "batch not found")
    items = db.execute(
        select(MigrationItem).where(MigrationItem.batch_id == batch_id)
    ).scalars().all()
    return {
        "batch": _batch_summary(b),
        "items": [
            {
                "id": it.id,
                "offer_id": it.offer_id,
                "name": it.name,
                "status": it.status,
                "mv_material_id": it.mv_material_id,
                "mv_barcode": it.mv_barcode,
                "upload_ref": it.upload_ref,
                "last_error": it.last_error,
            }
            for it in items
        ],
    }


@app.post("/api/batches")
def create_batch(req: CreateBatchRequest, db: Session = Depends(get_db)) -> dict:
    st = get_settings()
    if not st.ozon_client_id or not st.ozon_api_key:
        raise HTTPException(400, "OZON_CLIENT_ID / OZON_API_KEY not configured")
    from app.integrations.ozon_client import OzonSourceClient

    ozon = OzonSourceClient(
        client_id=st.ozon_client_id,
        api_key=st.ozon_api_key,
        base_url=st.ozon_api_base_url,
        timeout_seconds=st.ozon_timeout_seconds,
    )
    try:
        batch = pull_ozon_products(db, ozon, limit=req.limit, note=req.note)
    finally:
        ozon.close()
    return {"batch": _batch_summary(batch)}


@app.post("/api/batches/{batch_id}/run")
def run_batch(batch_id: int, db: Session = Depends(get_db)) -> dict:
    st = get_settings()
    b = db.get(MigrationBatch, batch_id)
    if b is None:
        raise HTTPException(404, "batch not found")
    if not (st.omni_api_key or st.mvideo_api_key):
        raise HTTPException(400, "OMNI_API_KEY not configured")

    from app.integrations.omni_client import OmniClient
    from app.ratelimit import RequestBudgeter

    budgeter = RequestBudgeter(db)
    omni = OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
        budgeter=budgeter,
    )
    try:
        prepare = run_prepare(db, batch_id=batch_id)
        images = run_images(db, batch_id=batch_id)
        templates = build_templates(db, batch_id=batch_id)
        mappings = poll_mappings(db, omni, batch_id=batch_id)
        # DRY-RUN by default: this route must not silently change price/stock.
        ps = apply_price_stock(db, omni, batch_id=batch_id, dry_run=True)
    finally:
        omni.close()
    summary = reconcile_batch(db, b)
    summary["stages"] = {
        "prepare": prepare,
        "images": images,
        "templates": templates,
        "mappings": mappings,
        "price_stock": ps,
    }
    return summary


@app.get("/api/report/{batch_id}")
def get_batch_report(batch_id: int, db: Session = Depends(get_db)) -> dict:
    """Aggregate status / needs_review detail for one migration batch."""
    try:
        return batch_report(db, batch_id)
    except LookupError:
        raise HTTPException(404, "batch not found")


@app.get("/api/orders")
def get_fbs_orders(limit: int = 100) -> dict:
    """Read-only FBS order view (no cancel / no status update).

    Returns an empty list + hint when no OMNI key is configured, instead of
    raising a 500.
    """
    st = get_settings()
    if not (st.omni_api_key or st.mvideo_api_key):
        return {"orders": [], "total": 0, "hint": "OMNI_API_KEY not configured"}

    from app.integrations.omni_client import OmniClient

    # Read-only call: no budgeter needed (budgeter only throttles writes).
    omni = OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
        budgeter=None,
    )
    try:
        view = list_fbs_orders(omni, {}, limit=limit)
    finally:
        omni.close()
    view["summary"] = summarize_orders(view.get("orders") or [])
    return view
