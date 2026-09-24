"""M.Video traditional API client (write side of the Ozon -> M.Video migration).

v0.2 (2026-09-18): aligned with the VERIFIED live OpenAPI
(https://api.sellers.mvideo.ru/openapi/api/main, v1.5.9):
- Auth header is now ``Api-Key: <key>`` (spec security scheme), no prefix.
- Every endpoint is read from ``app.endpoints.ENDPOINTS`` which now carries
  real paths, HTTP methods and path-parameter templates (``{taskCode}``/``{id}``).
- GET endpoints (dictionaries, material status, task info/errors/progress,
  readstock) are supported via ``_request()``, not the old all-POST wrapper.
- Body shapes match the spec: price/stock update take a bare JSON array
  (max 500); material create takes ``{"offerMappings": [...]}`` (max 50);
  material status takes ``GET /v2/material/{taskCode}/status``.
- The optional ``budgeter`` hook enforces the documented per-group 3h budgets
  from ``RATE_LIMIT_GROUPS`` via ``acquire(group)`` / ``record(group, ok)``.
- Security: the API key is stored in the httpx headers only. It is NEVER put
  into exception messages, logs, or repr output.

Public surface (one method per endpoints key):
  DictionaryV2: get_categories / get_attributes / get_attribute_values / get_product_types
  MaterialV2:   create_material / get_material_status / list_materials
  PriceV2:      update_prices
  StockV2:      update_stocks / get_stocks
  TaskV2:       get_task_info / get_task_errors / get_task_progress
  LinkageV2:    upsert_linkage / get_linkage_status / list_linkages
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx

from app.endpoints import (
    AUTH_HEADER_NAME,
    AUTH_HEADER_PREFIX,
    ENDPOINTS,
    group_of,
)


# --------------------------------------------------------------------------- #
# Exception hierarchy
# --------------------------------------------------------------------------- #
class MvideoError(Exception):
    """Base exception for all M.Video API failures."""


class MvideoAuthError(MvideoError):
    """The M.Video API rejected the supplied API key (401/403)."""


class MvideoRateLimitError(MvideoError):
    """The M.Video API rate limit was reached (429) or the budgeter blocked us."""


class MvideoClientError(MvideoError):
    """The M.Video API rejected a request (other 4xx response)."""


class MvideoServerError(MvideoError):
    """The M.Video API failed while processing a request (5xx response)."""


class MvideoTransportError(MvideoError):
    """A network or timeout failure occurred before a response was received."""


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class MvideoClient:
    """Client for the M.Video traditional (MaterialV2/PriceV2/...) API.

    Credentials are required and injected by the caller; this module neither
    reads secret files nor logs secret values.

    Parameters
    ----------
    api_key:
        The API-ключ created in ЛК -> меню учётной записи -> «Доступ к API».
    base_url:
        e.g. https://api.sellers.mvideo.ru  (production server from spec)
    vendor_id:
        Supplier id (vendorId); kept for EAN13 -> EAN18 conversion by the
        migration layer, not used for auth here.
    timeout_seconds:
        Per-request timeout.
    budgeter:
        Optional request-budget object exposing ``acquire(group)`` and
        ``record(group, ok)``. When present it gates every call.
    transport:
        httpx transport override (used by tests / mocks).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        vendor_id: str = "",
        timeout_seconds: float = 30.0,
        budgeter: Any = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not str(api_key).strip():
            raise ValueError("api_key is required")
        if not str(base_url).strip():
            raise ValueError("base_url is required")
        self._vendor_id = str(vendor_id or "")
        self._budgeter = budgeter
        self._http = httpx.Client(
            base_url=str(base_url).rstrip("/"),
            headers={
                AUTH_HEADER_NAME: f"{AUTH_HEADER_PREFIX}{api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    # -- lifecycle -------------------------------------------------------- #
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "MvideoClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Internal request plumbing
    # ------------------------------------------------------------------ #
    def _resolve(self, endpoint_key: str, **path_params: Any) -> str:
        try:
            spec = ENDPOINTS[endpoint_key]
        except KeyError as exc:
            raise MvideoClientError(f"unknown endpoint key: {endpoint_key}") from exc
        path: str = spec["path"]
        if path_params:
            try:
                path = path.format(**path_params)
            except (KeyError, ValueError) as exc:
                raise MvideoClientError(
                    f"invalid path params for {endpoint_key}: {sorted(path_params)}"
                ) from exc
        return path

    def _request(
        self,
        endpoint_key: str,
        *,
        method: str | None = None,
        payload: Any = None,
        **path_params: Any,
    ) -> Any:
        """Unified request: resolve path+method, throttle, map status -> error.

        The API key never appears in any raised message.
        """
        spec = ENDPOINTS[endpoint_key]
        method = (method or spec["method"]).upper()
        path = self._resolve(endpoint_key, **path_params)
        group = group_of(endpoint_key)

        if self._budgeter is not None:
            try:
                self._budgeter.acquire(group)
            except MvideoError:
                raise
            except Exception as exc:  # budgeter-internal failure -> rate-limit
                raise MvideoRateLimitError(f"budgeter refused group {group}") from exc

        try:
            if method == "GET":
                response = self._http.get(path)
            else:
                response = self._http.request(
                    method, path, content=None if payload is None else None,
                    json=None if payload is None else payload,
                )
        except httpx.TimeoutException as exc:
            if self._budgeter is not None:
                self._safe_record(group, False)
            raise MvideoTransportError("M.Video request timed out") from exc
        except httpx.HTTPError as exc:
            if self._budgeter is not None:
                self._safe_record(group, False)
            raise MvideoTransportError("M.Video transport request failed") from exc

        body_text = response.text[:2000] if response.status_code >= 400 else ""

        try:
            if response.status_code in (401, 403):
                raise MvideoAuthError(f"M.Video authentication failed (HTTP {response.status_code})")
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                suffix = f"; Retry-After={retry_after}" if retry_after else ""
                raise MvideoRateLimitError(f"M.Video rate limit reached (HTTP 429){suffix}")
            if 400 <= response.status_code < 500:
                raise MvideoClientError(
                    f"M.Video request failed (HTTP {response.status_code}): {body_text}"
                )
            if response.status_code >= 500:
                raise MvideoServerError(
                    f"M.Video service failed (HTTP {response.status_code}): {body_text}"
                )
        finally:
            if self._budgeter is not None:
                self._safe_record(group, response.status_code < 400)

        try:
            return response.json()
        except ValueError as exc:
            raise MvideoServerError("M.Video returned an invalid JSON response") from exc

    def _safe_record(self, group: str, ok: bool) -> None:
        try:
            self._budgeter.record(group, ok)  # type: ignore[union-attr]
        except Exception:
            pass  # budget bookkeeping must never break the request path

    # ------------------------------------------------------------------ #
    # DictionaryV2 (read)
    # ------------------------------------------------------------------ #
    def get_categories(self) -> list[dict[str, Any]]:
        """DictionaryV2: category tree. Use leaf-level categories only."""
        return self._request("dict.categories")

    def get_attributes(
        self, category_id: int, sales_scheme: str = "MARKETPLACE"
    ) -> dict[str, Any]:
        """DictionaryV2: consumer attributes for one leaf category."""
        path = self._resolve("dict.attributes")
        return self._http_get_extra(path, {"categoryId": category_id, "salesScheme": sales_scheme})

    def _http_get_extra(self, path: str, params: dict[str, Any]) -> Any:
        """GET with query params (bypasses _request because it needs params)."""
        group = group_of("dict.attributes")
        if self._budgeter is not None:
            try:
                self._budgeter.acquire(group)
            except MvideoError:
                raise
            except Exception as exc:
                raise MvideoRateLimitError(f"budgeter refused group {group}") from exc
        try:
            response = self._http.get(path, params=params)
        except httpx.TimeoutException as exc:
            if self._budgeter is not None:
                self._safe_record(group, False)
            raise MvideoTransportError("M.Video request timed out") from exc
        except httpx.HTTPError as exc:
            if self._budgeter is not None:
                self._safe_record(group, False)
            raise MvideoTransportError("M.Video transport request failed") from exc
        try:
            if response.status_code in (401, 403):
                raise MvideoAuthError(f"M.Video authentication failed (HTTP {response.status_code})")
            if response.status_code == 429:
                raise MvideoRateLimitError("M.Video rate limit reached (HTTP 429)")
            if 400 <= response.status_code < 500:
                raise MvideoClientError(
                    f"M.Video request failed (HTTP {response.status_code}): {response.text[:2000]}"
                )
            if response.status_code >= 500:
                raise MvideoServerError(
                    f"M.Video service failed (HTTP {response.status_code}): {response.text[:2000]}"
                )
        finally:
            if self._budgeter is not None:
                self._safe_record(group, response.status_code < 400)
        return response.json()

    def get_attribute_values(self, payload: dict[str, Any]) -> dict[str, Any]:
        """DictionaryV2: allowed enum values for LIST-type attributes."""
        return self._request("dict.attribute_values", payload=payload)

    def get_product_types(self) -> dict[str, Any]:
        """DictionaryV2: product type reference."""
        return self._request("dict.types")

    # ------------------------------------------------------------------ #
    # MaterialV2 (goods)
    # ------------------------------------------------------------------ #
    def create_material(self, offer_mappings: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """MaterialV2: submit a product create request. Body: {"offerMappings": [...]}."""
        offers = list(offer_mappings)
        if not offers:
            raise ValueError("create_material requires at least one offer")
        if len(offers) > 50:
            raise ValueError("create_material accepts at most 50 offers per call")
        return self._request("material.create", payload={"offerMappings": offers})

    def get_material_status(self, task_code: str) -> dict[str, Any]:
        """MaterialV2: status of a create task. GET /v2/material/{taskCode}/status."""
        if str(task_code).strip() == "":
            raise ValueError("task_code is required")
        return self._request("material.status", taskCode=str(task_code))

    def list_materials(
        self,
        *,
        material_codes: Iterable[str] | None = None,
        offer_ids: Iterable[str] | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """MaterialV2: read supplier goods. Body: {"filter": {...}, "cursor", "limit"}."""
        if limit < 1 or limit > 50:
            raise ValueError("limit must be in [1..50]")
        body: dict[str, Any] = {"limit": limit}
        flt: dict[str, Any] = {}
        if material_codes:
            flt["materialCodes"] = list(material_codes)
        if offer_ids:
            flt["offerIds"] = list(offer_ids)
        if flt:
            body["filter"] = flt
        if cursor:
            body["cursor"] = cursor
        return self._request("material.list", payload=body)

    # ------------------------------------------------------------------ #
    # PriceV2 / StockV2 (batch writes, bare JSON arrays, max 500 per call)
    # ------------------------------------------------------------------ #
    def update_prices(self, items: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """PriceV2: batch price update. Body is a bare array of UpdatePrice (max 500)."""
        batch = list(items)
        if not batch:
            raise ValueError("update_prices requires at least one item")
        if len(batch) > 500:
            raise ValueError("update_prices accepts at most 500 items per call")
        return self._request("price.update", payload=batch)

    def update_stocks(self, items: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """StockV2: batch stock update. Body is a bare array of UpdateStock (max 500)."""
        batch = list(items)
        if not batch:
            raise ValueError("update_stocks requires at least one item")
        if len(batch) > 500:
            raise ValueError("update_stocks accepts at most 500 items per call")
        return self._request("stock.update", payload=batch)

    def get_stocks(self) -> list[dict[str, Any]]:
        """StockV2: current stock / reserved / free (GET /v2/readstock)."""
        return self._request("stock.list")

    # ------------------------------------------------------------------ #
    # TaskV2 (async task introspection, GET)
    # ------------------------------------------------------------------ #
    def get_task_info(self, task_id: str) -> dict[str, Any]:
        if str(task_id).strip() == "":
            raise ValueError("task_id is required")
        return self._request("task.info", id=str(task_id))

    def get_task_errors(self, task_id: str) -> list[dict[str, Any]]:
        if str(task_id).strip() == "":
            raise ValueError("task_id is required")
        return self._request("task.errors", id=str(task_id))

    def get_task_progress(self, task_id: str) -> dict[str, Any]:
        if str(task_id).strip() == "":
            raise ValueError("task_id is required")
        return self._request("task.progress", id=str(task_id))

    # ------------------------------------------------------------------ #
    # LinkageV2 (multi-SKU)
    # ------------------------------------------------------------------ #
    def upsert_linkage(self, operations: Iterable[dict[str, Any]]) -> dict[str, Any]:
        ops = list(operations)
        if not ops:
            raise ValueError("upsert_linkage requires at least one operation")
        if len(ops) > 50:
            raise ValueError("upsert_linkage accepts at most 50 operations per call")
        return self._request("linkage.upsert", payload={"linkageOperations": ops})

    def get_linkage_status(self, task_code: str) -> dict[str, Any]:
        if str(task_code).strip() == "":
            raise ValueError("task_code is required")
        return self._request("linkage.status", taskCode=str(task_code))

    def list_linkages(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("linkage.list", payload=payload or {})

    # ------------------------------------------------------------------ #
    # Connection check
    # ------------------------------------------------------------------ #
    def check_connection(self) -> Any:
        """GET /v2/checking-connection — cheap auth sanity probe."""
        return self._request("check.connection")
