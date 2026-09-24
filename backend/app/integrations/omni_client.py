"""OMNI API (omni-net) client — v0.3 PRIMARY write channel.

Why a second client
-------------------
The traditional ``api.sellers.mvideo.ru`` MaterialV2/PriceV2/StockV2 endpoints
return ``400 API_KEY_INTERNAL_NOT_CONTAINS_KEY_TYPE`` for this seller account
(empirically verified 2026-09-18). The SAME key, sent as the ``api-key`` header
to ``https://omni-net.sellers.mvideo.ru``, authorizes price/stock writes
(empty-body POST returns 400 validation, not 401 auth). Product creation has
no OMNI endpoint — cards are created by uploading the Excel template to the
web ЛК (see pipeline/template_builder), and ``/v1/product/mapping/list`` is
then polled to recover ``product_id`` from our ``offer_id``.

Auth: header ``api-key: <MVIDEO_API_KEY>`` (no prefix).
Rate limit: POST/PUT/PATCH/DELETE under ``/v1/product`` and ``/v1/order`` are
300 req / 3 h, 5-min block on exceed (handled by the injected ``budgeter``).

Body shapes (from crawled doc D:\\Desktop\\mvideo\\_work\\omninet_api_doc.txt):
  POST /v1/product/price/update  {"items":[PriceUpdateItem 0..500], "currency":"RUB"}
        -> {"failed":[...]}            (currency contract lists CNY/USD/EUR but
                                       only RUB is honored by ЛКП)
  POST /v1/product/price/info    {"filter":{product_id[],offer_id[]},cursor,limit}
        -> {"prices":[...],next_cursor,total}
  POST /v1/product/stock/update {"items":[StockUpdateItem 0..500]}  -> {"failed":[...]}
  POST /v1/product/stock/info    {"filter":{product_id[],offer_id[],location_id[],is_archived},...}
  POST /v1/product/mapping/list {"filter":{product_id[],offer_id[],is_archived},cursor,limit}
        -> {"mappings":[{offer_id,product_id,...}],next_cursor,total}

Exception hierarchy mirrors app.integrations.mvideo_client (same base names,
omni prefix) so the pipeline can treat either channel uniformly. The key value
is stored only in the httpx headers and NEVER appears in messages/logs/repr.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

import httpx

from ..endpoints_omni import OMNI_AUTH_HEADER, PATHS, budget_group


# --------------------------------------------------------------------------- #
# Exception hierarchy (mirror of mvideo_client)
# --------------------------------------------------------------------------- #
class OmniError(Exception):
    """Base exception for all OMNI (omni-net) API failures."""


class OmniAuthError(OmniError):
    """The OMNI API rejected the api-key (401/403)."""


class OmniRateLimitError(OmniError):
    """The OMNI rate limit was reached (429) or the budgeter blocked us."""


class OmniClientError(OmniError):
    """The OMNI API rejected a request (other 4xx)."""


class OmniServerError(OmniError):
    """The OMNI API failed while processing a request (5xx)."""


class OmniTransportError(OmniError):
    """A network/timeout failure occurred before a response was received."""


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class OmniClient:
    """Typed httpx client for the M.Video OMNI (omni-net) API.

    Parameters mirror MvideoClient so the pipeline can inject either channel:

    api_key:         the same MVIDEO_API_KEY secret (sent as ``api-key``).
    base_url:        defaults to https://omni-net.sellers.mvideo.ru.
    timeout_seconds: per-request timeout.
    budgeter:        optional object with ``acquire(group)`` / ``record(group, ok)``.
    transport:       httpx transport override (tests / mocks).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        budgeter: Any = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not str(api_key).strip():
            raise ValueError("api_key is required")
        self._budgeter = budgeter
        self._http = httpx.Client(
            base_url=str(base_url or "https://omni-net.sellers.mvideo.ru").rstrip("/"),
            headers={
                OMNI_AUTH_HEADER: str(api_key),
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    # -- lifecycle -------------------------------------------------------- #
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OmniClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Internal request plumbing (status -> typed exception, key never logged)
    # ------------------------------------------------------------------ #
    def _post(self, endpoint_key: str, payload: Any) -> Any:
        path = PATHS[endpoint_key]
        group = budget_group(path)

        if self._budgeter is not None:
            try:
                self._budgeter.acquire(group)
            except OmniError:
                raise
            except Exception as exc:  # budgeter-internal failure -> rate limit
                raise OmniRateLimitError(f"budgeter refused group {group}") from exc

        try:
            response = self._http.post(path, json=payload)
        except httpx.TimeoutException as exc:
            self._record(group, path, 0, False)
            raise OmniTransportError("OMNI request timed out") from exc
        except httpx.HTTPError as exc:
            self._record(group, path, 0, False)
            raise OmniTransportError("OMNI transport request failed") from exc

        body_text = response.text[:2000] if response.status_code >= 400 else ""
        status = response.status_code
        try:
            if response.status_code in (401, 403):
                raise OmniAuthError(f"OMNI authentication failed (HTTP {response.status_code})")
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                suffix = f"; Retry-After={retry_after}" if retry_after else ""
                raise OmniRateLimitError(f"OMNI rate limit reached (HTTP 429){suffix}")
            if 400 <= response.status_code < 500:
                raise OmniClientError(
                    f"OMNI request failed (HTTP {response.status_code}): {body_text}"
                )
            if response.status_code >= 500:
                raise OmniServerError(
                    f"OMNI service failed (HTTP {response.status_code}): {body_text}"
                )
        finally:
            # Full budgeter contract: record(group, action=path, status, banned).
            # A 429 is recorded as a ban so the sliding window blocks us for the
            # documented 5 minutes; transport failures record status 0.
            self._record(group, path, status, banned=(status == 429))

        try:
            return response.json()
        except ValueError as exc:
            raise OmniServerError("OMNI returned an invalid JSON response") from exc

    def _record(self, group: str, action: str, status: int, banned: bool) -> None:
        try:
            self._budgeter.record(group, action, status_code=int(status),
                                   banned=bool(banned))
        except Exception:
            pass  # budget bookkeeping must never break the request path

    # ------------------------------------------------------------------ #
    # Prices
    # ------------------------------------------------------------------ #
    def price_update(self, items: Iterable[dict[str, Any]], currency: str = "RUB") -> dict[str, Any]:
        """POST /v1/product/price/update. items: PriceUpdateItem list (max 500).

        ``currency`` is forced to RUB: the omni-net contract lists CNY/USD/EUR
        but ЛКП only honors RUB. Returns ``{"failed":[...]}``.
        """
        batch = list(items)
        if not batch:
            raise ValueError("price_update requires at least one item")
        if len(batch) > 500:
            raise ValueError("price_update accepts at most 500 items per call")
        if currency != "RUB":
            raise ValueError("OMNI price update only supports currency=RUB")
        resp = self._post("price.update", {"items": batch, "currency": currency})
        return resp if isinstance(resp, dict) else {"failed": []}

    def price_info(self, filter: dict[str, Any], *, cursor: str | None = None, limit: int = 100) -> dict[str, Any]:
        """POST /v1/product/price/info. filter: {product_id[], offer_id[]}."""
        body: dict[str, Any] = {"filter": filter or {}, "limit": int(limit)}
        if cursor:
            body["cursor"] = cursor
        resp = self._post("price.info", body)
        return resp if isinstance(resp, dict) else {}

    # ------------------------------------------------------------------ #
    # Stock
    # ------------------------------------------------------------------ #
    def stock_update(self, items: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """POST /v1/product/stock/update. items: StockUpdateItem list (max 500)."""
        batch = list(items)
        if not batch:
            raise ValueError("stock_update requires at least one item")
        if len(batch) > 500:
            raise ValueError("stock_update accepts at most 500 items per call")
        resp = self._post("stock.update", {"items": batch})
        return resp if isinstance(resp, dict) else {"failed": []}

    def stock_info(self, filter: dict[str, Any], *, cursor: str | None = None, limit: int = 100) -> dict[str, Any]:
        """POST /v1/product/stock/info. filter: {product_id[],offer_id[],location_id[]}."""
        body: dict[str, Any] = {"filter": filter or {}, "limit": int(limit)}
        if cursor:
            body["cursor"] = cursor
        resp = self._post("stock.info", body)
        return resp if isinstance(resp, dict) else {}

    # ------------------------------------------------------------------ #
    # Identity mapping (offer_id <-> product_id)
    # ------------------------------------------------------------------ #
    def mapping_list(
        self,
        filter: dict[str, Any] | None = None,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """POST /v1/product/mapping/list -> {mappings, next_cursor, total}."""
        body: dict[str, Any] = {"filter": filter or {}, "limit": int(limit)}
        if cursor:
            body["cursor"] = cursor
        return self._post("mapping.list", body)

    def iter_mappings(
        self,
        filter: dict[str, Any] | None = None,
        *,
        limit: int = 500,
    ) -> Iterator[dict[str, Any]]:
        """Generator over ALL mappings, following ``next_cursor`` pages.

        Each yielded mapping is the raw dict (keys include ``offer_id`` and
        ``product_id`` per the OMNI snake_case contract). ``limit`` is the
        per-page size.
        """
        cursor: str | None = None
        while True:
            page = self.mapping_list(filter, cursor=cursor, limit=limit)
            mappings = page.get("mappings") or []
            for m in mappings:
                if isinstance(m, dict):
                    yield m
            cursor = page.get("next_cursor") or None
            if not cursor or not mappings:
                break

    # ------------------------------------------------------------------ #
    # FBS Orders (read-only)
    # ------------------------------------------------------------------ #
    def order_fbs_list(
        self,
        body: dict[str, Any] | None = None,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        """POST /v1/order/fbs/list -> raw response dict.

        Read-only: returns a page of FBS orders. The exact body shape
        (cursor / filter) is passed through as-is; callers in
        ``order_service.list_fbs_orders`` normalise the result.
        """
        payload: dict[str, Any] = dict(body or {})
        payload["limit"] = int(limit)
        return self._post("order.fbs.list", payload)

    # ------------------------------------------------------------------ #
    # Connection check (cheap auth sanity probe)
    # ------------------------------------------------------------------ #
    def check_connection(self) -> bool:
        """True iff the api-key is accepted.

        Uses a read-only stock/info probe with an EMPTY filter: empirically
        POST /v1/product/stock/info with {"filter":{},"limit":1} returns 200
        for an authorized Omniom key (mapping/list with empty filter returns
        400 «Некорректный запрос», so it is NOT a valid auth probe). Raises
        nothing on auth success; returns False on auth/transport failure so
        callers can embed it in /health without crashing.
        """
        try:
            resp = self.stock_info({}, limit=1)
            return isinstance(resp, dict)
        except OmniAuthError:
            return False
        except OmniTransportError:
            return False
        except OmniError:
            return False
