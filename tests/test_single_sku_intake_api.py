"""Contract tests for the independent Ozon single-SKU intake API."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import SingleSkuJob, SingleSkuStatus

API_PATH = "/api/v1/integrations/ozon/single-sku-jobs"
TEST_INTEGRATION_KEY = "test-integration-secret"


def sample_request() -> dict:
    return {
        "schema_version": "ozon.single-sku.v1",
        "idempotency_key": "ozon-1237743084-TQBSM1",
        "source": {
            "url": "https://www.ozon.ru/product/1237743084/",
            "product_id": "1237743084",
            "sku_id": "TQBSM1",
            "title": "Станок для резки монтажной ленты TQBSM1",
            "description": "Диспенсер TQBSM1 для монтажной ленты.",
            "brand": "Acme",
            "model": "TQBSM1",
            "price_rub": 1999,
            "category": {
                "id": 17029021,
                "name": "Диспенсеры для монтажной ленты",
            },
            "packageInfo": {
                "weightG": 400,
                "lengthMm": 130,
                "widthMm": 65,
                "heightMm": 80,
            },
            "material": "Силикон",
            "images": [
                "https://example.com/main.jpg",
                "https://example.com/second.jpg",
            ],
        },
    }


@pytest.fixture()
def api_client(memory_session, monkeypatch):
    monkeypatch.setenv("INTEGRATION_API_KEY", TEST_INTEGRATION_KEY)
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: memory_session
    client = TestClient(app)
    try:
        yield client, memory_session
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_missing_or_invalid_key_is_rejected(api_client) -> None:
    client, _ = api_client

    missing = client.post(API_PATH, json=sample_request())
    invalid = client.post(
        API_PATH,
        json=sample_request(),
        headers={"X-Integration-Key": "wrong-key"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_unconfigured_server_key_returns_503(memory_session, monkeypatch) -> None:
    monkeypatch.delenv("INTEGRATION_API_KEY", raising=False)
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: memory_session
    client = TestClient(app)

    try:
        response = client.post(
            API_PATH,
            json=sample_request(),
            headers={"X-Integration-Key": "anything"},
        )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_valid_request_creates_awaiting_input_job(api_client) -> None:
    client, session = api_client

    response = client.post(
        API_PATH,
        json=sample_request(),
        headers={"X-Integration-Key": TEST_INTEGRATION_KEY},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] is True
    assert body["status"] == SingleSkuStatus.AWAITING_INPUT
    assert body["schema_version"] == "ozon.single-sku.v1"
    assert body["idempotency_key"] == "ozon-1237743084-TQBSM1"
    assert body["source"]["platform"] == "ozon"
    assert body["source"]["product_id"] == "1237743084"
    assert body["source"]["sku_id"] == "TQBSM1"
    assert TEST_INTEGRATION_KEY not in response.text

    job = session.execute(select(SingleSkuJob)).scalar_one()
    assert job.job_ref == body["job_ref"]
    assert job.status == SingleSkuStatus.AWAITING_INPUT
    assert job.source_price_rub == Decimal("1999.00")
    assert job.purchase_cost_cny is None
    assert job.stock is None
    assert job.cost_confirmed is False
    assert job.stock_confirmed is False
    assert job.dry_run_result_json == {}
    assert job.upload_ref == ""
    assert job.uploaded_at is None


def test_duplicate_source_returns_same_job_with_200(api_client) -> None:
    client, _ = api_client
    headers = {"X-Integration-Key": TEST_INTEGRATION_KEY}

    first = client.post(API_PATH, json=sample_request(), headers=headers)
    second = client.post(API_PATH, json=sample_request(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["job_ref"] == first.json()["job_ref"]


def test_same_idempotency_key_with_different_source_conflicts(api_client) -> None:
    client, _ = api_client
    headers = {"X-Integration-Key": TEST_INTEGRATION_KEY}
    first = client.post(API_PATH, json=sample_request(), headers=headers)
    assert first.status_code == 201

    changed = deepcopy(sample_request())
    changed["source"]["product_id"] = "1237743085"
    changed["source"]["sku_id"] = "TQBSM2"
    changed["source"]["url"] = "https://www.ozon.ru/product/1237743085/"
    response = client.post(API_PATH, json=changed, headers=headers)

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "product_id"), ""),
        (("source", "sku_id"), ""),
        (("source", "url"), "not-a-url"),
        (("source", "packageInfo", "weightG"), 0),
        (("source", "packageInfo", "lengthMm"), 0),
        (("source", "images"), []),
    ],
)
def test_invalid_source_payload_is_rejected(api_client, path, value) -> None:
    client, _ = api_client
    request = sample_request()
    target = request
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    response = client.post(
        API_PATH,
        json=request,
        headers={"X-Integration-Key": TEST_INTEGRATION_KEY},
    )

    assert response.status_code == 422


def test_get_existing_job(api_client) -> None:
    client, _ = api_client
    headers = {"X-Integration-Key": TEST_INTEGRATION_KEY}
    created = client.post(API_PATH, json=sample_request(), headers=headers)
    job_ref = created.json()["job_ref"]

    response = client.get(f"{API_PATH}/{job_ref}", headers=headers)

    assert response.status_code == 200
    assert response.json()["job_ref"] == job_ref
    assert response.json()["status"] == SingleSkuStatus.AWAITING_INPUT


def test_get_missing_job_returns_404(api_client) -> None:
    client, _ = api_client
    response = client.get(
        f"{API_PATH}/SSKU-NOT-FOUND",
        headers={"X-Integration-Key": TEST_INTEGRATION_KEY},
    )

    assert response.status_code == 404


def test_idempotency_key_from_other_platform_conflicts(api_client) -> None:
    client, session = api_client
    request = sample_request()
    other_platform_job = SingleSkuJob(
        job_ref="SSKU-OTHER-1",
        source_platform="other",
        source_url="https://example.com/other",
        source_product_id="other-product",
        source_sku_id="other-sku",
        idempotency_key=request["idempotency_key"],
    )
    session.add(other_platform_job)
    session.commit()

    response = client.post(
        API_PATH,
        json=request,
        headers={"X-Integration-Key": TEST_INTEGRATION_KEY},
    )

    assert response.status_code == 409


def test_natural_key_is_enforced_by_database(memory_session) -> None:
    from sqlalchemy.exc import IntegrityError

    first = SingleSkuJob(
        job_ref="SSKU-DUP-1",
        source_platform="ozon",
        source_product_id="same-product",
        source_sku_id="same-sku",
    )
    second = SingleSkuJob(
        job_ref="SSKU-DUP-2",
        source_platform="ozon",
        source_product_id="same-product",
        source_sku_id="same-sku",
    )
    memory_session.add_all([first, second])

    with pytest.raises(IntegrityError):
        memory_session.commit()
    memory_session.rollback()


def test_ensure_indexes_upgrades_legacy_single_sku_table(tmp_path) -> None:
    from sqlalchemy import create_engine, inspect, text

    from backend.app.database import ensure_single_sku_jobs_indexes

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-mvideo.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE single_sku_jobs (
                    id INTEGER PRIMARY KEY,
                    source_platform TEXT,
                    source_product_id TEXT,
                    source_sku_id TEXT,
                    idempotency_key TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO single_sku_jobs (
                    source_platform,
                    source_product_id,
                    source_sku_id,
                    idempotency_key
                ) VALUES (
                    'ozon',
                    'product-1',
                    'sku-1',
                    'key-1'
                )
                """
            )
        )

    ensure_single_sku_jobs_indexes(engine)
    ensure_single_sku_jobs_indexes(engine)

    index_names = {
        index["name"]
        for index in inspect(engine).get_indexes("single_sku_jobs")
    }
    assert "ix_single_sku_jobs_idempotency_key" in index_names
    assert "uq_single_sku_jobs_source" in index_names


@pytest.mark.parametrize(
    "rows",
    [
        (
            "('ozon', 'product-1', 'sku-1', 'duplicate-key')",
            "('ozon', 'product-2', 'sku-2', 'duplicate-key')",
        ),
        ("(' ', 'product-1', 'sku-1', 'key-1')",),
        (
            "('ozon', 'same-product', 'same-sku', 'key-1')",
            "('ozon', 'same-product', 'same-sku', 'key-2')",
        ),
    ],
)
def test_ensure_indexes_rejects_unsafe_legacy_data(tmp_path, rows) -> None:
    from sqlalchemy import create_engine, text

    from backend.app.database import ensure_single_sku_jobs_indexes

    engine = create_engine(f"sqlite:///{tmp_path / 'unsafe-legacy.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE single_sku_jobs (
                    id INTEGER PRIMARY KEY,
                    source_platform TEXT,
                    source_product_id TEXT,
                    source_sku_id TEXT,
                    idempotency_key TEXT
                )
                """
            )
        )
        for row in rows:
            conn.execute(
                text(
                    f"""
                    INSERT INTO single_sku_jobs (
                        source_platform,
                        source_product_id,
                        source_sku_id,
                        idempotency_key
                    ) VALUES {row}
                    """
                )
            )

    with pytest.raises(RuntimeError):
        ensure_single_sku_jobs_indexes(engine)
