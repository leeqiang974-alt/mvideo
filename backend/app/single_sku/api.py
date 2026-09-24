"""Versioned Ozon -> M.Video single-SKU intake API.

This boundary is intentionally narrow: it validates a versioned source
contract and creates or reads an awaiting-input job. It does not invoke
pricing, dry-run Excel generation, or upload logic.
"""

from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..models import SingleSkuJob
from .workflow import create_job_from_ozon_payload

SCHEMA_VERSION = "ozon.single-sku.v1"

router = APIRouter(prefix="/api/v1/integrations/ozon", tags=["integrations-ozon"])


class OzonSourceCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=512)


class OzonPackageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weightG: Decimal = Field(gt=0)
    lengthMm: Decimal = Field(gt=0)
    widthMm: Decimal = Field(gt=0)
    heightMm: Decimal = Field(gt=0)


class OzonSingleSkuSource(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: HttpUrl
    product_id: str = Field(min_length=1, max_length=128)
    sku_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1)
    description: str = ""
    brand: str = ""
    model: str = ""
    price_rub: Decimal | None = Field(default=None, gt=0)
    category: OzonSourceCategory
    packageInfo: OzonPackageInfo
    material: str = ""
    images: list[HttpUrl] = Field(min_length=1, max_length=15)

    @field_validator("url")
    @classmethod
    def require_https_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("source URL must use HTTPS")
        return value

    @field_validator("images")
    @classmethod
    def require_https_images(cls, value: list[HttpUrl]) -> list[HttpUrl]:
        for image_url in value:
            if image_url.scheme != "https":
                raise ValueError("image URLs must use HTTPS")
        return value


class CreateSingleSkuJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ozon.single-sku.v1"]
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    source: OzonSingleSkuSource


class SourceIdentity(BaseModel):
    platform: str
    url: str
    product_id: str
    sku_id: str


class SingleSkuJobResponse(BaseModel):
    job_ref: str
    schema_version: str
    idempotency_key: str | None
    status: str
    created: bool
    source: SourceIdentity


def require_integration_key(
    integration_key: str | None = Header(default=None, alias="X-Integration-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Authenticate machine-to-machine callers."""
    if not settings.integration_api_key:
        raise HTTPException(503, "integration API key is not configured")
    if not integration_key:
        raise HTTPException(401, "missing integration API key")
    if not secrets.compare_digest(integration_key, settings.integration_api_key):
        raise HTTPException(401, "invalid integration API key")


def _find_by_natural_key(
    db: Session, source: OzonSingleSkuSource
) -> SingleSkuJob | None:
    return db.execute(
        select(SingleSkuJob)
        .where(
            SingleSkuJob.source_platform == "ozon",
            SingleSkuJob.source_product_id == source.product_id,
            SingleSkuJob.source_sku_id == source.sku_id,
        )
        .limit(1)
    ).scalar_one_or_none()


def _find_by_idempotency_key(
    db: Session, idempotency_key: str
) -> SingleSkuJob | None:
    return db.execute(
        select(SingleSkuJob).where(SingleSkuJob.idempotency_key == idempotency_key)
    ).scalar_one_or_none()


def _serialize_job(job: SingleSkuJob, *, created: bool) -> dict:
    return {
        "job_ref": job.job_ref,
        "schema_version": job.schema_version or SCHEMA_VERSION,
        "idempotency_key": job.idempotency_key,
        "status": job.status,
        "created": created,
        "source": {
            "platform": job.source_platform,
            "url": job.source_url,
            "product_id": job.source_product_id,
            "sku_id": job.source_sku_id,
        },
    }


@router.post(
    "/single-sku-jobs",
    response_model=SingleSkuJobResponse,
    status_code=201,
    responses={200: {"model": SingleSkuJobResponse}},
    dependencies=[Depends(require_integration_key)],
)
def create_single_sku_job(
    request: CreateSingleSkuJobRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    source = request.source
    existing_by_key: SingleSkuJob | None = None

    if request.idempotency_key:
        existing_by_key = _find_by_idempotency_key(db, request.idempotency_key)
        if existing_by_key and (
            existing_by_key.source_platform != "ozon"
            or existing_by_key.source_product_id != source.product_id
            or existing_by_key.source_sku_id != source.sku_id
        ):
            raise HTTPException(409, "idempotency key reused with a different source")

    existing = existing_by_key or _find_by_natural_key(db, source)
    if existing is not None:
        return JSONResponse(
            content=_serialize_job(existing, created=False),
            status_code=200,
        )

    source_data = source.model_dump(mode="json", by_alias=True)
    try:
        job = create_job_from_ozon_payload(
            db,
            source_data,
            schema_version=request.schema_version,
            idempotency_key=request.idempotency_key,
        )
    except IntegrityError as exc:
        db.rollback()
        existing = (
            _find_by_idempotency_key(db, request.idempotency_key)
            if request.idempotency_key
            else None
        )
        existing = existing or _find_by_natural_key(db, source)
        if existing is not None:
            return JSONResponse(
                content=_serialize_job(existing, created=False),
                status_code=200,
            )
        raise HTTPException(409, "single-SKU job conflict") from exc

    return JSONResponse(
        content=_serialize_job(job, created=True),
        status_code=201,
    )


@router.get(
    "/single-sku-jobs/{job_ref}",
    response_model=SingleSkuJobResponse,
    dependencies=[Depends(require_integration_key)],
)
def get_single_sku_job(
    job_ref: str,
    db: Session = Depends(get_db),
) -> dict:
    job = db.execute(
        select(SingleSkuJob).where(SingleSkuJob.job_ref == job_ref)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "single-SKU job not found")
    return _serialize_job(job, created=False)
