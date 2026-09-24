"""Tests for the OMNI (omni-net) client — v0.3.

Uses httpx.MockTransport so no real network is touched. A fake budgeter records
acquire()/record() calls to prove the throttle hook is wired correctly.
"""

import json

import httpx
import pytest

from backend.app.integrations.omni_client import (
    OmniAuthError,
    OmniClient,
    OmniClientError,
    OmniRateLimitError,
    OmniServerError,
)


class FakeBudgeter:
    """Records acquire()/record() calls for assertion."""

    def __init__(self) -> None:
        self.acquired: list[str] = []
        self.records: list[dict] = []
        self.wait_seconds = 0.0

    def acquire(self, group: str) -> float:
        self.acquired.append(group)
        return float(self.wait_seconds)

    def record(self, method_group: str, action: object = "",
               status_code: int = 0, banned: bool = False) -> None:
        self.records.append(
            {"group": method_group, "action": str(action),
             "status_code": int(status_code), "banned": bool(banned)}
        )


def _make_client(handler, budgeter=None) -> OmniClient:
    return OmniClient(
        api_key="secret-test-key",
        base_url="https://omnet.example.test",
        timeout_seconds=5.0,
        budgeter=budgeter,
        transport=httpx.MockTransport(handler),
    )


# --------------------------------------------------------------------------- #
# price_update: path / header / currency body
# --------------------------------------------------------------------------- #
def test_price_update_sends_correct_shape():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["api_key"] = request.headers.get("api-key")
        seen["content_type"] = request.headers.get("content-type")
        body = json.loads(request.content.decode("utf-8"))
        seen["body"] = body
        return httpx.Response(200, json={"failed": []})

    client = _make_client(handler)
    resp = client.price_update(
        [{"offer_id": "SKU00259-1", "price": 100.0, "currency": "RUB"}],
        currency="RUB",
    )
    client.close()

    assert seen["path"] == "/v1/product/price/update"
    assert seen["api_key"] == "secret-test-key"
    assert "application/json" in (seen["content_type"] or "")
    assert seen["body"]["currency"] == "RUB"
    assert len(seen["body"]["items"]) == 1
    assert seen["body"]["items"][0]["offer_id"] == "SKU00259-1"
    assert resp == {"failed": []}


def test_price_update_rejects_oversize_batch():
    client = _make_client(lambda req: httpx.Response(200, json={"failed": []}))
    with pytest.raises(ValueError):
        client.price_update([{}] * 501)
    with pytest.raises(ValueError):
        client.price_update([])
    client.close()


# --------------------------------------------------------------------------- #
# mapping auto-pagination
# --------------------------------------------------------------------------- #
def test_iter_mappings_paginates():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append(body)
        if body.get("cursor"):
            return httpx.Response(200, json={
                "mappings": [{"offer_id": "SKU-B", "product_id": 222}],
                "next_cursor": "",
                "total": 2,
            })
        return httpx.Response(200, json={
            "mappings": [{"offer_id": "SKU-A", "product_id": 111}],
            "next_cursor": "cursor-page-2",
            "total": 2,
        })

    client = _make_client(handler)
    out = list(client.iter_mappings(filter={}, limit=100))
    client.close()

    assert [m["offer_id"] for m in out] == ["SKU-A", "SKU-B"]
    assert calls[0].get("cursor", "") == ""
    assert calls[1]["cursor"] == "cursor-page-2"


# --------------------------------------------------------------------------- #
# status-code -> typed exception mapping
# --------------------------------------------------------------------------- #
def test_429_raises_rate_limit_and_records_ban():
    budgeter = FakeBudgeter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate"})

    client = _make_client(handler, budgeter=budgeter)
    with pytest.raises(OmniRateLimitError):
        client.mapping_list(filter={}, limit=1)
    client.close()

    # banned=True recorded on 429
    assert budgeter.records and budgeter.records[-1]["banned"] is True
    assert budgeter.records[-1]["status_code"] == 429


def test_401_raises_auth():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = _make_client(handler)
    with pytest.raises(OmniAuthError):
        client.mapping_list(filter={}, limit=1)
    client.close()


def test_check_connection_false_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = _make_client(handler)
    assert client.check_connection() is False
    client.close()


def test_check_connection_true_on_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"mappings": [], "next_cursor": "", "total": 0})

    client = _make_client(handler)
    assert client.check_connection() is True
    client.close()


def test_other_4xx_is_client_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    client = _make_client(handler)
    with pytest.raises(OmniClientError):
        client.price_update([{"offer_id": "x"}], currency="RUB")
    client.close()


def test_5xx_is_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _make_client(handler)
    with pytest.raises(OmniServerError):
        client.mapping_list(filter={}, limit=1)
    client.close()


# --------------------------------------------------------------------------- #
# budgeter acquire/record wiring
# --------------------------------------------------------------------------- #
def test_budgeter_acquired_and_recorded():
    budgeter = FakeBudgeter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"failed": []})

    client = _make_client(handler, budgeter=budgeter)
    client.price_update([{"offer_id": "x"}], currency="RUB")
    client.close()

    # price/update lives under /v1/product
    assert budgeter.acquired == ["/v1/product"]
    last = budgeter.records[-1]
    assert last["group"] == "/v1/product"
    assert last["action"] == "/v1/product/price/update"
    assert last["status_code"] == 200
    assert last["banned"] is False


def test_budgeter_none_does_not_crash():
    client = _make_client(
        lambda req: httpx.Response(200, json={"failed": []}),
        budgeter=None,
    )
    resp = client.stock_update([{"offer_id": "x", "stock": 5}])
    client.close()
    assert resp == {"failed": []}


def test_stock_update_body_shape():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode("utf-8"))
        seen["path"] = request.url.path
        return httpx.Response(200, json={"failed": []})

    client = _make_client(handler)
    client.stock_update([{"offer_id": "SKU00259-2", "stock": 3}])
    client.close()

    assert seen["path"] == "/v1/product/stock/update"
    assert seen["body"] == {"items": [{"offer_id": "SKU00259-2", "stock": 3}]}
