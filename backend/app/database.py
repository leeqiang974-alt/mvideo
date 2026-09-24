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
        }
    else:
        column_types = {
            "template_file_path": "TEXT",
            "image_status": "VARCHAR(32)",
            "upload_ref": "VARCHAR(128)",
            "uploaded_at": "TIMESTAMP",
            "compliance_documents_json": "JSON",
            "color": "VARCHAR(64)",
        }

    for column_name, column_type in column_types.items():
        if column_name in existing:
            continue
        ddl = text(
            f"ALTER TABLE single_sku_jobs ADD COLUMN {column_name} {column_type}"
        )
        with bind.begin() as conn:
            conn.execute(ddl)
