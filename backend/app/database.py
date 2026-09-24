"""Engine / session factory. SQLite by default (zero infra), Postgres optional.

Borrowed pattern from the Ozon ERP: SQLite runs single-writer so use NullPool +
busy_timeout + foreign_keys ON; Postgres uses pool_pre_ping.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
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
