"""Operator-facing review API for the independent single-SKU workflow."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SingleSkuJob
from .pricing import PricingError
from .workflow import (
    PROJECT_ROOT,
    SingleSkuWorkflowError,
    convert_package_dimensions,
    prepare_dry_run,
)

router = APIRouter(prefix="/api/v1", tags=["single-sku-review"])
ALLOWED_EXCEL_DIR = (PROJECT_ROOT / "work" / "single_sku").resolve()
XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


class DryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_cost_cny: Decimal | None = None
    stock: int | None = None
    color: str | None = None
    target_net_margin: Decimal | None = None
    shipping_channel: str | None = None
    tn_ved: str | None = None
    compliance_documents: list[str | dict[str, Any]] = Field(default_factory=list)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _blockers(job: SingleSkuJob) -> list[str]:
    if str(job.status or "").lower() != "blocked":
        return []
    return [
        part.strip()
        for part in str(job.last_error or "").split(";")
        if part.strip()
    ]


def _converted_package(job: SingleSkuJob) -> dict[str, str] | None:
    try:
        converted = convert_package_dimensions(
            length_mm=job.length_mm,
            width_mm=job.width_mm,
            height_mm=job.height_mm,
            weight_g=job.weight_g,
        )
    except (PricingError, TypeError, ValueError):
        return None
    return _json_safe(converted)


def serialize_job(job: SingleSkuJob) -> dict[str, Any]:
    return {
        "job_ref": job.job_ref,
        "schema_version": job.schema_version,
        "idempotency_key": job.idempotency_key,
        "status": job.status,
        "source": {
            "platform": job.source_platform,
            "url": job.source_url,
            "product_id": job.source_product_id,
            "sku_id": job.source_sku_id,
            "title": job.source_title,
            "description": job.source_description,
            "brand": job.source_brand,
            "model": job.source_model,
            "price_rub": job.source_price_rub,
            "images": job.source_images_json or [],
            "payload": job.source_payload_json or {},
        },
        "category": {
            "ozon_category_id": job.ozon_category_id,
            "ozon_category_name": job.ozon_category_name,
            "mv_group_id": job.mv_group_id,
            "mv_group_name": job.mv_group_name,
            "mv_infomodel_id": job.mv_infomodel_id,
            "commission_category": job.commission_category,
            "tn_ved": job.tn_ved,
            "certificate_requirements": job.certificate_requirements_json or [],
            "compliance_documents": job.compliance_documents_json or [],
        },
        "package": {
            "length_mm": job.length_mm,
            "width_mm": job.width_mm,
            "height_mm": job.height_mm,
            "weight_g": job.weight_g,
            "converted": _converted_package(job),
        },
        "review_inputs": {
            "purchase_cost_cny": job.purchase_cost_cny,
            "domestic_cost_cny": job.domestic_cost_cny,
            "stock": job.stock,
            "color": job.color,
            "cost_confirmed": job.cost_confirmed,
            "dimensions_confirmed": job.dimensions_confirmed,
            "stock_confirmed": job.stock_confirmed,
            "category_confirmed": job.category_confirmed,
            "compliance_confirmed": job.compliance_confirmed,
        },
        "pricing": {
            "target_net_margin": job.target_net_margin,
            "shipping_channel": job.shipping_channel,
            "price_rub": job.price_rub,
            "result": job.pricing_result_json or {},
        },
        "content": {
            "brand": job.brand,
            "sanitized_title": job.sanitized_title,
            "sanitized_description": job.sanitized_description,
            "quality_report": job.quality_report_json or {},
        },
        "dry_run": job.dry_run_result_json or {},
        "upload": {
            "upload_ref": job.upload_ref,
            "uploaded_at": job.uploaded_at,
            "upload_performed": bool(job.upload_ref),
        },
        "blockers": _blockers(job),
    }


def _get_job_or_404(db: Session, job_ref: str) -> SingleSkuJob:
    job = db.execute(
        select(SingleSkuJob).where(SingleSkuJob.job_ref == job_ref)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="single-SKU job not found")
    return job


@router.get("/single-sku-jobs/{job_ref}")
def get_single_sku_job(
    job_ref: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = _get_job_or_404(db, job_ref)
    return {"job": _json_safe(serialize_job(job))}


@router.post("/single-sku-jobs/{job_ref}/dry-run")
def create_single_sku_dry_run(
    request: DryRunRequest,
    job_ref: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = _get_job_or_404(db, job_ref)
    try:
        job = prepare_dry_run(
            db,
            job,
            purchase_cost_cny=request.purchase_cost_cny,
            stock=request.stock,
            color=request.color,
            target_net_margin=request.target_net_margin,
            shipping_channel=request.shipping_channel,
            compliance_documents=request.compliance_documents,
            tn_ved=request.tn_ved,
        )
    except SingleSkuWorkflowError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "blockers": exc.blockers,
            },
        ) from exc

    return {
        "job": _json_safe(serialize_job(job)),
        "dry_run": _json_safe(job.dry_run_result_json),
    }


@router.get("/single-sku-jobs/{job_ref}/dry-run/workbook")
def download_single_sku_workbook(
    job_ref: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    job = _get_job_or_404(db, job_ref)
    result = job.dry_run_result_json or {}
    raw_output_path = result.get("output_file_path")

    if not isinstance(raw_output_path, str) or not raw_output_path.strip():
        raise HTTPException(
            status_code=409,
            detail="dry-run workbook has not been generated",
        )

    output_path = Path(raw_output_path).resolve()
    if output_path.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=403, detail="invalid workbook path")
    try:
        output_path.relative_to(ALLOWED_EXCEL_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="workbook path is outside work/single_sku") from exc

    if not output_path.is_file():
        raise HTTPException(status_code=404, detail="dry-run workbook file not found")

    return FileResponse(
        output_path,
        media_type=XLSX_MEDIA_TYPE,
        filename=output_path.name,
    )