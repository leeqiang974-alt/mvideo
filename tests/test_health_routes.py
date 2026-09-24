from __future__ import annotations

from types import SimpleNamespace

import app.integrations.omni_client as omni_module
import app.main as main_module


class _ScalarResult:
    def scalar_one_or_none(self):
        return None


class _FakeSession:
    def get_bind(self):
        return object()

    def execute(self, _statement):
        return _ScalarResult()


def test_base_health_does_not_probe_external_integrations(monkeypatch):
    def fail_if_settings_are_loaded():
        raise AssertionError("base health must not load external integration settings")

    monkeypatch.setattr(main_module, "get_settings", fail_if_settings_are_loaded)
    monkeypatch.setattr(
        main_module,
        "sa_inspect",
        lambda _bind: SimpleNamespace(
            get_table_names=lambda: ["migration_items", "migration_batches"]
        ),
    )
    result = main_module.health(_FakeSession())

    assert result["ok"] is True
    assert result["omni_ok"] is None
    assert result["omni_status"] == "not_checked"
    assert result["tables_present"] == ["migration_batches", "migration_items"]
    assert result["table_count"] == 2


def test_omni_health_reports_not_configured_without_building_client(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(omni_api_key="", mvideo_api_key=""),
    )

    class FailClient:
        def __init__(self, **_kwargs):
            raise AssertionError("client must not be created without a key")

    monkeypatch.setattr(omni_module, "OmniClient", FailClient)

    assert main_module.omni_health() == {
        "ok": True,
        "omni_ok": None,
        "status": "not_configured",
    }


def test_omni_health_checks_connection_and_closes_client(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(
            omni_api_key="configured",
            mvideo_api_key="",
            omni_api_base_url="https://example.invalid",
            omni_timeout_seconds=7,
        ),
    )

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def check_connection(self):
            calls.append("checked")
            return True

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(omni_module, "OmniClient", FakeClient)

    assert main_module.omni_health() == {
        "ok": True,
        "omni_ok": True,
        "status": "connected",
    }
    assert calls == [
        {
            "api_key": "configured",
            "base_url": "https://example.invalid",
            "timeout_seconds": 7,
        },
        "checked",
        "closed",
    ]


def test_omni_health_reports_unavailable_and_still_closes(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(
            omni_api_key="configured",
            mvideo_api_key="",
            omni_api_base_url="https://example.invalid",
            omni_timeout_seconds=7,
        ),
    )

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def check_connection(self):
            calls.append("checked")
            return False

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(omni_module, "OmniClient", FakeClient)

    assert main_module.omni_health() == {
        "ok": False,
        "omni_ok": False,
        "status": "unavailable",
    }
    assert calls == ["checked", "closed"]
