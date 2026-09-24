"""Pytest shared fixtures. Ensures the project root is on sys.path so
``backend.app.*`` imports resolve, and provides an in-memory SQLite session
for the table-driven budgeter tests.
"""

import os
import sys

# project root = parent of tests/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# backend/ is also a package root: the live integrations import as
# ``app.endpoints_omni`` / ``app.endpoints`` (backend on sys.path), while the
# tests import as ``backend.app.*``. Putting both on path keeps both working.
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import pytest  # noqa: E402


@pytest.fixture()
def memory_session():
    """Fresh in-memory SQLite with all MvideoERP tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.app.database import Base
    from backend.app import models  # noqa: F401  (register tables)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()
