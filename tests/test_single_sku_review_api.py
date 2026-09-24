"""Contract tests for the operator single-SKU review API."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import CategoryMapping, SingleSkuJob
from backend.app.single_sku.workflow import PROJECT_ROOT

JOB_REF = "SSKU-TEST-1"
API_PATH = f"/api/v1/single-sku-jobs/{JOB_REF}"


@pytest.fixture()
def review_client(memory_session):
    app.dependency_overrides[get_db] = lambda: memory_session
    client = TestClient(app)
    try:
        yield client, memory_session
    finally:
        app.dependency_overrides.clear()


def seed_job(session) -> SingleSkuJob:
    session.add(
        CategoryMapping(
            ozon_category_id=17029021,
            ozon_category_name="Диспенсеры для монтажной ленты",
            mv_group_id="604171101",
            mv_group_name="Диспенсеры для монтажной ленты",
            mv_infomodel_id="INF-307590",
            status="confirmed",
        )
    )
    job = SingleSkuJob(
        job_ref=JOB_REF,
        source_platform="ozon",
        source_url="https://www.ozon.ru/product/1237743084/",
        source_product_id="1237743084",
        source_sku_id="TQBSM1",
        source_title="Acme Станок для резки монтажной ленты TQBSM1",
        source_description="Acme диспенсер TQBSM1 для монтажной ленты.",
        source_brand="Acme",
        source_model="TQBSM1",
        source_price_rub=Decimal("1999.00"),
        source_images_json=[
            "https://example.com/main.jpg",
            "https://example.com/second.jpg",
        ],
        source_payload_json={
            "material": "Силикон",
            "packageInfo": {
                "weightG": 400,
                "lengthMm": 130,
                "widthMm": 65,
                "heightMm": 80,
            },
        },
        ozon_category_id=17029021,
        ozon_category_name="Диспенсеры для монтажной ленты",
        commission_category="home",
        length_mm=Decimal("130"),
        width_mm=Decimal("65"),
        height_mm=Decimal("80"),
        weight_g=Decimal("400"),
        color="белый",
        status="awaiting_input",
    )
    session.add(job)
    session.commit()
    return job


def test_get_job_details(review_client) -> None:
    client, session = review_client
    seed_job(session)

    response = client.get(API_PATH)

    assert response.status_code == 200, response.text
    job = response.json()["job"]
    assert job["job_ref"] == JOB_REF
    assert job["status"] == "awaiting_input"
    assert job["source"]["price_rub"] == "1999.00"
    assert job["source"]["images"] == [
        "https://example.com/main.jpg",
        "https://example.com/second.jpg",
    ]
    assert job["review_inputs"]["purchase_cost_cny"] is None
    converted = job["package"]["converted"]
    assert Decimal(converted["length_cm"]) == Decimal("13")
    assert Decimal(converted["width_cm"]) == Decimal("6.5")
    assert Decimal(converted["height_cm"]) == Decimal("8")
    assert Decimal(converted["weight_kg"]) == Decimal("0.4")
    assert job["upload"]["upload_performed"] is False
    assert job["blockers"] == []


def test_valid_confirmation_creates_dry_run_and_workbook(review_client) -> None:
    client, session = review_client
    seed_job(session)

    response = client.post(
        f"{API_PATH}/dry-run",
        json={
            "purchase_cost_cny": "12.34",
            "stock": 5,
            "color": "фиолетовый",
            "target_net_margin": "0.25",
            "shipping_channel": "economy",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    job = body["job"]
    dry_run = body["dry_run"]

    assert job["status"] == "dry_run_ready"
    assert job["review_inputs"]["purchase_cost_cny"] == "12.3400"
    assert job["review_inputs"]["stock"] == 5
    assert job["review_inputs"]["cost_confirmed"] is True
    assert job["review_inputs"]["stock_confirmed"] is True
    assert job["pricing"]["price_rub"]
    assert job["upload"]["upload_ref"] == ""
    assert job["upload"]["uploaded_at"] is None
    assert job["upload"]["upload_performed"] is False
    assert dry_run["upload_performed"] is False
    assert dry_run["upload_ref"] == ""
    assert dry_run["source_price_rub_used_as_cny_cost"] is False
    assert dry_run["column_count"] == 95

    workbook = client.get(f"{API_PATH}/dry-run/workbook")
    assert workbook.status_code == 200, workbook.text
    assert workbook.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert workbook.content[:2] == b"PK"
    assert "dry_run_" in workbook.headers["content-disposition"]
    assert JOB_REF.lower() in workbook.headers["content-disposition"].lower()


def test_missing_purchase_cost_blocks_job(review_client) -> None:
    client, session = review_client
    seed_job(session)

    response = client.post(f"{API_PATH}/dry-run", json={"stock": 5})

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert any("CNY" in blocker for blocker in detail["blockers"])

    refreshed = client.get(API_PATH)
    job = refreshed.json()["job"]
    assert job["status"] == "blocked"
    assert any("CNY" in blocker for blocker in job["blockers"])
    assert job["review_inputs"]["purchase_cost_cny"] is None


def test_extra_fields_are_rejected(review_client) -> None:
    client, session = review_client
    seed_job(session)

    response = client.post(
        f"{API_PATH}/dry-run",
        json={"stock": 5, "unexpected_field": "x"},
    )

    assert response.status_code == 422


def test_workbook_not_generated_returns_409(review_client) -> None:
    client, session = review_client
    seed_job(session)

    response = client.get(f"{API_PATH}/dry-run/workbook")

    assert response.status_code == 409


def test_workbook_path_cannot_leave_allowed_directory(review_client) -> None:
    client, session = review_client
    job = seed_job(session)
    outside_path = (
        PROJECT_ROOT / "work" / "downloads" / "_test_oss.xlsx"
    ).resolve()
    job.dry_run_result_json = {"output_file_path": str(outside_path)}
    session.commit()

    response = client.get(f"{API_PATH}/dry-run/workbook")

    assert response.status_code == 403