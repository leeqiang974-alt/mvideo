"""ORM models for the M.Video ERP.

State machines are REWRITTEN for M.Video semantics (do NOT copy Ozon's):
- Success = moderation approved (Готов к продаже) AND price + stock set.
- Rejection loop = «С ошибками» -> fix card -> resubmit.
- 7 field groups are locked after approval -> pre-validate before submit.
- Barcode: marketplace type uses EAN18; EAN13 input auto-converts.
- Quota: replaced by a sliding-window request budget (300 req / 3h).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ---- Status enums (strings stored in DB) -----------------------------------

class BatchStatus:
    RUNNING = "running"               # creating / submitting
    MODERATING = "moderating"         # items under moderation
    WAITING_QUOTA = "waiting_quota"   # request budget exhausted / ban window
    NEEDS_REVIEW = "needs_review"     # rejected items need manual fix
    DONE = "done"                     # all items terminal
    PAUSED = "paused"
    FAILED = "failed"


class ItemStatus:
    QUEUED = "queued"                 # pulled from Ozon, not yet quality-gated
    PREPARED = "prepared"             # passed quality gate
    # --- v0.3: Excel-template upload pipeline (OMNI has no product-create endpoint) ---
    IMAGES_PROCESSED = "images_processed"  # 3:4 processed + OSS URLs ready
    TEMPLATE_BUILT = "template_built"      # filled .xlsx row ready to upload
    TEMPLATE_UPLOADED = "template_uploaded"  # uploaded to /mpa/products/import
    MAPPING_PENDING = "mapping_pending"     # polling /v1/product/mapping/list
    PRODUCT_MATCHED = "product_matched"     # offer_id -> product_id resolved
    PRICED = "priced"                 # OMNI price/update done (RUB)
    STOCKED = "stocked"               # OMNI stock/update done -> item SUCCESS
    NEEDS_REVIEW = "needs_review"     # template rejected / card error, fix & re-upload
    FAILED = "failed"                 # unrecoverable
    SKIPPED = "skipped"               # deliberately skipped
    WAITING_QUOTA = "waiting_quota"   # request budget / ban pause

class SingleSkuStatus:
    """Independent single-SKU workflow statuses.

    This enum must not be merged into MigrationBatch / MigrationItem.
    """

    AWAITING_INPUT = "awaiting_input"
    PRICED = "priced"
    DRY_RUN_READY = "dry_run_ready"
    BLOCKED = "blocked"


# legacy v0.2 MaterialV2 states (kept so old rows still parse; pipeline v0.3 bypasses them)
class LegacyMaterialStatus:
    SUBMITTED = "submitted"           # MaterialV2 create accepted (DEPRECATED channel)
    ON_MODERATION = "on_moderation"   # polling «На модерации» (DEPRECATED)
    READY_TO_SELL = "ready_to_sell"   # «Готов к продаже» (DEPRECATED)


# terminal success states
SUCCESS_STATES = {ItemStatus.STOCKED}
# states that mean the card already exists on M.Video side
LIVE_STATES = {
    ItemStatus.TEMPLATE_UPLOADED,
    ItemStatus.MAPPING_PENDING,
    ItemStatus.PRODUCT_MATCHED,
    ItemStatus.PRICED,
    ItemStatus.STOCKED,
    ItemStatus.NEEDS_REVIEW,
}


class MigrationBatch(Base):
    __tablename__ = "migration_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="ozon")
    status: Mapped[str] = mapped_column(String(32), default=BatchStatus.RUNNING, index=True)
    note: Mapped[str] = mapped_column(Text, default="")

    total_count: Mapped[int] = mapped_column(Integer, default=0)
    submitted_count: Mapped[int] = mapped_column(Integer, default=0)
    on_moderation_count: Mapped[int] = mapped_column(Integer, default=0)
    ready_count: Mapped[int] = mapped_column(Integer, default=0)
    priced_count: Mapped[int] = mapped_column(Integer, default=0)
    stocked_count: Mapped[int] = mapped_column(Integer, default=0)
    errored_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["MigrationItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )

    def reconcile_counts(self) -> None:
        """Write-then-reconcile: sum counts across items must equal total."""
        rows = [
            (ItemStatus.MAPPING_PENDING, "on_moderation_count"),
            (ItemStatus.PRODUCT_MATCHED, "ready_count"),
            (ItemStatus.PRICED, "priced_count"),
            (ItemStatus.STOCKED, "stocked_count"),
            (ItemStatus.NEEDS_REVIEW, "errored_count"),
            (ItemStatus.FAILED, "failed_count"),
            (ItemStatus.SKIPPED, "skipped_count"),
        ]
        for status, attr in rows:
            setattr(self, attr, sum(1 for i in self.items if i.status == status))
        self.submitted_count = sum(
            1 for i in self.items if i.status in LIVE_STATES
        )


class MigrationItem(Base):
    __tablename__ = "migration_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "ozon_product_id", name="uq_item_batch_ozon"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("migration_batches.id"), index=True)

    # --- source (Ozon) ---
    ozon_product_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    offer_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    name: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str] = mapped_column(String(255), default="")
    ozon_category_id: Mapped[int] = mapped_column(Integer, default=0)
    ozon_category_name: Mapped[str] = mapped_column(String(512), default="")
    attributes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    images_json: Mapped[list] = mapped_column(JSON, default=list)
    source_barcode: Mapped[str] = mapped_column(String(64), default="")

    # --- target (M.Video) ---
    mv_group_id: Mapped[str] = mapped_column(String(64), default="")
    mv_infomodel_id: Mapped[str] = mapped_column(String(64), default="")
    mv_material_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    mv_product_id: Mapped[str] = mapped_column(String(64), default="", index=True)  # OMNI product_id (v0.3.2)
    mv_sap_code: Mapped[str] = mapped_column(String(64), default="")  # materialCode from moderation
    mv_warehouse_code: Mapped[str] = mapped_column(String(64), default="")  # R-объект for stock
    mv_barcode: Mapped[str] = mapped_column(String(64), default="")  # read back / EAN18
    mv_tn_ved: Mapped[str] = mapped_column(String(32), default="")
    mv_nds: Mapped[str] = mapped_column(String(16), default="")
    # Pack dimensions (M.Video template cols 14-17): cm / kg, derived from Ozon
    # v4 top-level width/height/depth(mm)/weight(g).
    mv_length_cm: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    mv_width_cm: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    mv_height_cm: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    mv_weight_kg: Mapped[float] = mapped_column(Numeric(10, 3), default=0)
    mv_description: Mapped[str] = mapped_column(Text, default="")
    # v0.3: Excel-import upload reference (upload-history row) + OSS image urls
    upload_ref: Mapped[str] = mapped_column(String(128), default="")
    oss_images_json: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(
        String(32), default=ItemStatus.QUEUED, index=True
    )
    moderation_status: Mapped[str] = mapped_column(String(64), default="")
    moderation_errors: Mapped[list] = mapped_column(JSON, default=list)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict)

    price_rub: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    price_set: Mapped[bool] = mapped_column(default=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    stock_set: Mapped[bool] = mapped_column(default=False)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    batch: Mapped[MigrationBatch] = relationship(back_populates="items")


class RequestBudgetEvent(Base):
    """One row per outbound write call, used by the sliding-window budgeter."""
    __tablename__ = "request_budget_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    method_group: Mapped[str] = mapped_column(String(32), index=True)  # MaterialV2/PriceV2/...
    action: Mapped[str] = mapped_column(String(64), default="")
    status_code: Mapped[int] = mapped_column(Integer, default=0)
    banned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CategoryMapping(Base):
    __tablename__ = "category_mappings"
    __table_args__ = (
        UniqueConstraint("ozon_category_id", name="uq_cat_ozon"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ozon_category_id: Mapped[int] = mapped_column(Integer, index=True)
    ozon_category_name: Mapped[str] = mapped_column(String(512), default="")
    mv_group_id: Mapped[str] = mapped_column(String(64), default="")
    mv_group_name: Mapped[str] = mapped_column(String(512), default="")
    mv_infomodel_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|ready|needs_review
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AttributeMapping(Base):
    __tablename__ = "attribute_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    ozon_attr_key: Mapped[str] = mapped_column(String(128), index=True)
    mv_feature_id: Mapped[str] = mapped_column(String(64), default="")
    mv_feature_name: Mapped[str] = mapped_column(String(512), default="")
    value_map: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Certificate(Base):
    """ФЗ-289 quality documents (СГР/РУ/ДС/СС). Stub storage; upload handled later."""
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    cert_type: Mapped[str] = mapped_column(String(16), default="")  # СГР/РУ/ДС/СС
    reg_number: Mapped[str] = mapped_column(String(128), default="")
    registry_status: Mapped[str] = mapped_column(String(32), default="")  # Действующий
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, default="")
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("migration_items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KVCache(Base):
    """Generic dictionary cache (M.Video categories/features/enums)."""
    __tablename__ = "kv_cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SingleSkuJob(Base):
    """One source product/SKU to one M.Video product/SKU.

    This is intentionally separate from MigrationBatch and MigrationItem.
    Source RUB prices are evidence only and never become CNY purchase cost.
    """

    __tablename__ = "single_sku_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_platform: Mapped[str] = mapped_column(String(32), default="ozon")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    source_product_id: Mapped[str] = mapped_column(String(128), default="")
    source_sku_id: Mapped[str] = mapped_column(String(128), default="")
    source_title: Mapped[str] = mapped_column(Text, default="")
    source_description: Mapped[str] = mapped_column(Text, default="")
    source_brand: Mapped[str] = mapped_column(String(255), default="")
    source_model: Mapped[str] = mapped_column(String(255), default="")
    source_price_rub: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    source_images_json: Mapped[list] = mapped_column(JSON, default=list)
    source_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)

    ozon_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ozon_category_name: Mapped[str] = mapped_column(String(512), default="")
    mv_group_id: Mapped[str] = mapped_column(String(64), default="")
    mv_group_name: Mapped[str] = mapped_column(String(512), default="")
    mv_infomodel_id: Mapped[str] = mapped_column(String(64), default="")
    commission_category: Mapped[str] = mapped_column(String(64), default="other")
    tn_ved: Mapped[str] = mapped_column(String(64), default="")
    certificate_requirements_json: Mapped[list] = mapped_column(JSON, default=list)
    compliance_documents_json: Mapped[list] = mapped_column(JSON, default=list)

    purchase_cost_cny: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    domestic_cost_cny: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    length_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    height_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str] = mapped_column(String(64), default="белый")

    cost_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    dimensions_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    category_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    target_net_margin: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.25")
    )
    shipping_channel: Mapped[str] = mapped_column(String(16), default="economy")
    price_rub: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    pricing_result_json: Mapped[dict] = mapped_column(JSON, default=dict)

    brand: Mapped[str] = mapped_column(String(128), default="Нет бренда")
    sanitized_title: Mapped[str] = mapped_column(Text, default="")
    sanitized_description: Mapped[str] = mapped_column(Text, default="")
    quality_report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    dry_run_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    template_file_path: Mapped[str] = mapped_column(Text, default="")
    image_status: Mapped[str] = mapped_column(String(32), default="source_only")
    upload_ref: Mapped[str] = mapped_column(String(128), default="")
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=SingleSkuStatus.AWAITING_INPUT, index=True
    )
    last_error: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    price_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dry_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
