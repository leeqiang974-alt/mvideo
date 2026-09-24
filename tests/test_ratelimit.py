"""Tests for RequestBudgeter (v0.1). In-memory SQLite, table-driven."""

from types import SimpleNamespace

from backend.app.ratelimit import RequestBudgeter


def _settings(max_req=10, window=10800, ban=300, headroom=0.9):
    return SimpleNamespace(
        rl_window_seconds=window,
        rl_max_requests=max_req,
        rl_ban_seconds=ban,
        rl_safety_headroom=headroom,
    )


class TestAcquire:
    def test_empty_allows(self, memory_session):
        b = RequestBudgeter(memory_session, _settings())
        assert b.acquire("MaterialV2") == 0.0

    def test_blocks_at_threshold(self, memory_session):
        s = _settings(max_req=10, headroom=0.9)  # threshold = 9
        b = RequestBudgeter(memory_session, s)
        for _ in range(9):
            b.record("MaterialV2", "material.create", status_code=200)
        # count == threshold -> must wait (window 10800s)
        wait = b.acquire("MaterialV2")
        assert wait > 0.0
        assert wait <= s.rl_window_seconds

    def test_independent_groups(self, memory_session):
        s = _settings(max_req=10, headroom=0.9)
        b = RequestBudgeter(memory_session, s)
        for _ in range(9):
            b.record("MaterialV2", "material.create", status_code=200)
        # PriceV2 untouched -> still free
        assert b.acquire("PriceV2") == 0.0

    def test_failed_writes_not_counted(self, memory_session):
        s = _settings(max_req=10, headroom=0.9)  # threshold 9
        b = RequestBudgeter(memory_session, s)
        # 429 responses recorded as errors (NOT as a full ban) -> they must
        # not consume the successful-write budget, and no ban window applies.
        for _ in range(9):
            b.record("MaterialV2", "material.create", status_code=429, banned=False)
        assert b.acquire("MaterialV2") == 0.0


class TestBan:
    def test_active_ban_returns_remaining(self, memory_session):
        s = _settings(max_req=10, ban=300)
        b = RequestBudgeter(memory_session, s)
        b.record("MaterialV2", "material.create", status_code=429, banned=True)
        wait = b.acquire("MaterialV2")
        # ~300s left, tiny elapsed subtracted
        assert 290 < wait <= 300
