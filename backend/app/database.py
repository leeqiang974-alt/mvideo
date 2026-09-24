"""Engine / session factory. SQLite by default (zero infra), Postgres optional.

Borrowed pattern from the Ozon ERP: SQLite runs single-writer so use NullPool +
busy_timeout + foreign_keys ON; Postgres uses pool_pre_ping.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from .config import get_settings

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 60} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    poolclass=NullPool if _is_sqlite else None,
    pool_pre_ping=not _is_sqlite,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec) -> None:  # pragma: no cover - engine setup
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA busy_timeout = 60000")
            cur.execute("PRAGMA foreign_keys = ON")
        finally:
            cur.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Idempotent."""
    from . import models  # noqa: F401  (ensure models are imported on Base.metadata)

    Base.metadata.create_all(bind=engine)
    ensure_single_sku_jobs_columns(engine)
    ensure_single_sku_jobs_indexes(engine)


def ensure_single_sku_jobs_columns(bind) -> None:
    """Add columns introduced after the first single-SKU table release.

    The project supports SQLite by default and Postgres in production. New
    columns are nullable: application defaults remain on the ORM model, while
    historical rows are safely left as NULL instead of being rewritten.
    """
    inspector = inspect(bind)
    if not inspector.has_table("single_sku_jobs"):
        return

    existing = {column["name"] for column in inspector.get_columns("single_sku_jobs")}
    dialect = bind.dialect.name
    if dialect == "postgresql":
        column_types = {
            "template_file_path": "TEXT",
            "image_status": "VARCHAR(32)",
            "upload_ref": "VARCHAR(128)",
            "uploaded_at": "TIMESTAMP",
            "compliance_documents_json": "JSON",
            "color": "VARCHAR(64)",
            "schema_version": "VARCHAR(32) DEFAULT ''",
            "idempotency_key": "VARCHAR(128)",
        }
    else:
        column_types = {
            "template_file_path": "TEXT",
            "image_status": "VARCHAR(32)",
            "upload_ref": "VARCHAR(128)",
            "uploaded_at": "TIMESTAMP",
            "compliance_documents_json": "JSON",
            "color": "VARCHAR(64)",
            "schema_version": "VARCHAR(32) DEFAULT ''",
            "idempotency_key": "VARCHAR(128)",
        }

    for column_name, column_type in column_types.items():
        if column_name in existing:
            continue
        ddl = text(
            f"ALTER TABLE single_sku_jobs ADD COLUMN {column_name} {column_type}"
        )
        with bind.begin() as conn:
            conn.execute(ddl)

def ensure_single_sku_jobs_indexes(bind) -> None:
    """Create uniqueness indexes used by the versioned intake API.

    New databases receive these constraints from the ORM model. Existing
    SQLite/Postgres databases are upgraded conservatively: duplicate or
    incomplete source identities fail migration instead of being silently
    merged.
    """
    table = "single_sku_jobs"
    inspector = inspect(bind)
    if not inspector.has_table(table):
        return

    index_names = {index["name"] for index in inspector.get_indexes(table)}
    unique_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table)
    }
    existing_names = index_names | unique_names

    with bind.begin() as conn:
        duplicate_idempotency = conn.execute(
            text(
                """
                SELECT COUNT(*) AS duplicate_groups
                FROM (
                    SELECT idempotency_key
                    FROM single_sku_jobs
                    WHERE COALESCE(TRIM(idempotency_key), '') <> ''
                    GROUP BY idempotency_key
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
        if duplicate_idempotency:
            raise RuntimeError(
                "cannot create unique single-SKU idempotency index: "
                f"{duplicate_idempotency} duplicate idempotency key group(s) "
                "must be reconciled first"
            )

        invalid_natural = conn.execute(
            text(
                """
                SELECT COUNT(*) AS invalid_rows
                FROM single_sku_jobs
                WHERE COALESCE(TRIM(source_platform), '') = ''
                   OR COALESCE(TRIM(source_product_id), '') = ''
                   OR COALESCE(TRIM(source_sku_id), '') = ''
                """
            )
        ).scalar_one()
        if invalid_natural:
            raise RuntimeError(
                "cannot create unique single-SKU source index: "
                f"{invalid_natural} job(s) have incomplete source identities "
                "and must be reconciled first"
            )

        duplicate_natural = conn.execute(
            text(
                """
                SELECT COUNT(*) AS duplicate_groups
                FROM (
                    SELECT source_platform, source_product_id, source_sku_id
                    FROM single_sku_jobs
                    WHERE COALESCE(TRIM(source_platform), '') <> ''
                      AND COALESCE(TRIM(source_product_id), '') <> ''
                      AND COALESCE(TRIM(source_sku_id), '') <> ''
                    GROUP BY source_platform, source_product_id, source_sku_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
        if duplicate_natural:
            raise RuntimeError(
                "cannot create unique single-SKU source index: "
                f"{duplicate_natural} duplicate source group(s) "
                "must be reconciled first"
            )

        if "ix_single_sku_jobs_idempotency_key" not in existing_names:
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX ix_single_sku_jobs_idempotency_key
                    ON single_sku_jobs (idempotency_key)
                    WHERE COALESCE(TRIM(idempotency_key), '') <> ''
                    """
                )
            )

        if "uq_single_sku_jobs_source" not in existing_names:
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX uq_single_sku_jobs_source
                    ON single_sku_jobs (
                        source_platform,
                        source_product_id,
                        source_sku_id
                    )
                    """
                )
            )