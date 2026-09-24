"""Sliding-window request budgeter for M.Video writes.

v0.2 (2026-09-18): per-group budgets from the VERIFIED live OpenAPI
(https://api.sellers.mvideo.ru/openapi/api/main):
  MaterialV2    1000 req / 3h
  PriceV2        300 req / 3h
  StockV2        300 req / 3h
  LinkageV2     1000 req / 3h
  DictionaryV2  1000 req / 3h
  5-min block on breach.
Group defaults come from ``app.endpoints.RATE_LIMIT_GROUPS``; env overrides
(RL_MAX_REQUESTS) still act as a global safety cap.
- Pure table-driven: every outbound write call calls ``record()``; every
  call that wants to send first calls ``acquire()`` which returns the
  seconds to wait (0 = go now).  No in-memory state, so it survives
  restarts and is trivially unit-testable against an in-memory SQLite DB.

Backwards-compat bridge for the client (which calls
``record(group, ok_bool)``): a boolean second positional arg is mapped to
a (status_code, banned) pair so both calling styles bookkeep correctly.
``acquire()`` is non-blocking by contract; the HTTP layer should sleep on
the returned seconds before sending.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from .config import Settings, get_settings
from .endpoints import RATE_LIMIT_GROUPS
from .models import RequestBudgetEvent


class RequestBudgeter:
    def __init__(self, session, settings: Settings | None = None) -> None:
        self.session = session
        s = settings or get_settings()
        self.global_window_seconds = s.rl_window_seconds
        self.global_max_requests = s.rl_max_requests
        self.ban_seconds = s.rl_ban_seconds
        self.headroom = s.rl_safety_headroom
        self.groups = dict(RATE_LIMIT_GROUPS)

    def _limits(self, method_group: str) -> tuple[int, int]:
        """(max_requests, window_seconds) for a group; global env as a cap."""
        req, win = self.groups.get(method_group, (self.global_max_requests, self.global_window_seconds))
        # env override caps the group budget if set lower
        if self.global_max_requests != 300:
            req = min(req, self.global_max_requests)
        return req, win

    # ------------------------------------------------------------------
    def _recent_since(self, method_group: str) -> datetime:
        _, win = self._limits(method_group)
        return datetime.utcnow() - timedelta(seconds=win)

    def _count_active_writes(self, method_group: str) -> int:
        """Successful (non-banned, non-error) writes inside the window."""
        since = self._recent_since(method_group)
        stmt = (
            select(func.count())
            .select_from(RequestBudgetEvent)
            .where(RequestBudgetEvent.method_group == method_group)
            .where(RequestBudgetEvent.banned.is_(False))
            .where(RequestBudgetEvent.status_code < 400)
            .where(RequestBudgetEvent.created_at >= since)
        )
        return int(self.session.execute(stmt).scalar_one())

    def _oldest_active_created_at(self, method_group: str) -> datetime | None:
        since = self._recent_since(method_group)
        stmt = (
            select(func.min(RequestBudgetEvent.created_at))
            .where(RequestBudgetEvent.method_group == method_group)
            .where(RequestBudgetEvent.banned.is_(False))
            .where(RequestBudgetEvent.status_code < 400)
            .where(RequestBudgetEvent.created_at >= since)
        )
        return self.session.execute(stmt).scalar_one()

    def _latest_ban(self, method_group: str) -> datetime | None:
        stmt = (
            select(func.max(RequestBudgetEvent.created_at))
            .where(RequestBudgetEvent.method_group == method_group)
            .where(RequestBudgetEvent.banned.is_(True))
        )
        return self.session.execute(stmt).scalar_one()

    # ------------------------------------------------------------------
    def acquire(self, method_group: str) -> float:
        """Seconds to wait before sending. 0 = allowed to send now."""
        now = datetime.utcnow()
        max_req, win = self._limits(method_group)
        threshold = int(max_req * self.headroom)

        # 1) active ban window takes precedence
        last_ban = self._latest_ban(method_group)
        if last_ban is not None:
            elapsed = (now - last_ban).total_seconds()
            if elapsed < self.ban_seconds:
                return float(self.ban_seconds - elapsed)

        # 2) sliding window budget
        count = self._count_active_writes(method_group)
        if count < threshold:
            return 0.0

        # at/over threshold: wait until the oldest in-window write ages out
        oldest = self._oldest_active_created_at(method_group)
        if oldest is None:
            return 0.0
        wait = win - (now - oldest).total_seconds()
        return max(0.0, wait)

    def record(
        self,
        method_group: str,
        action: object = "",
        status_code: int = 0,
        banned: bool = False,
    ) -> RequestBudgetEvent:
        """Persist one outbound write outcome.

        Contract call: record(group, action="", status_code=200, banned=False).
        Legacy client call: record(group, ok_bool) -- a boolean second arg is
        bridged here: True -> (status 200, not banned), False -> (status 500,
        not banned, so it does not count as a successful active write).
        """
        if isinstance(action, bool):
            status_code = 200 if action else 500
            action = ""
        evt = RequestBudgetEvent(
            method_group=method_group,
            action=str(action),
            status_code=int(status_code),
            banned=bool(banned),
        )
        self.session.add(evt)
        self.session.commit()
        return evt
