"""Ozon Seller API client (READ-ONLY source for the Ozon -> M.Video migration).

v0.1 (2026-09-17)

Mirrors the MvideoClient style: httpx.Client, injected credentials, typed
exceptions, context manager. Ozon auth is the well-known
``Client-Id`` + ``Api-Key`` header pair. The key is NEVER logged or echoed.

Public surface (one method per Ozon Seller API route):
  iter_products(limit=100)   generator over /v2/product/list pagination
  get_product_info(ids)      /v2/product/info/list
  get_product_attributes(ids) /v3/products/info/attributes
  get_product_images(ids)    /v3/product/info/images
  get_prices(ids)            /v4/product/info/prices
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx


class OzonSourceError(Exception):
    """Base error for all Ozon read failures."""


class OzonAuthError(OzonSourceError):
    """Ozon rejected Client-Id / Api-Key (401/403)."""


class OzonClientError(OzonSourceError):
    """Ozon rejected the request (4xx)."""


class OzonServerError(OzonSourceError):
    """Ozon failed while processing (5xx)."""


class OzonTransportError(OzonSourceError):
    """Network / timeout failure before a response."""


class OzonSourceClient:
    """Read-only Ozon Seller client. Credentials injected by the caller."""

    def __init__(
        self,
        *,
        client_id: str,
        api_key: str,
        base_url: str = "https://api-seller.ozon.ru",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not str(client_id).strip():
            raise ValueError("client_id is required")
        if not str(api_key).strip():
            raise ValueError("api_key is required")
        self._http = httpx.Client(
            base_url=str(base_url).rstrip("/"),
            headers={
                "Client-Id": str(client_id),
                "Api-Key": str(api_key),
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OzonSourceClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._http.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise OzonTransportError("Ozon request timed out") from exc
        except httpx.HTTPError as exc:
            raise OzonTransportError("Ozon transport request failed") from exc

        body_text = response.text[:2000] if response.status_code >= 400 else ""
        if response.status_code in (401, 403):
            raise OzonAuthError(f"Ozon authentication failed (HTTP {response.status_code})")
        if 400 <= response.status_code < 500:
            raise OzonClientError(f"Ozon request failed (HTTP {response.status_code}): {body_text}")
        if response.status_code >= 500:
            raise OzonServerError(f"Ozon service failed (HTTP {response.status_code}): {body_text}")

        try:
            body = response.json()
        except ValueError as exc:
            raise OzonServerError("Ozon returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise OzonServerError("Ozon returned an unexpected response shape")
        return body

    # ------------------------------------------------------------------ #
    def iter_products(self, limit: int = 100):
        """Yield every product list item, paging with ``last_id``."""
        if limit < 1:
            raise ValueError("limit must be >= 1")
        last_id = ""
        while True:
            body = self._post(
                "/v3/product/list",
                {"filter": {"visibility": "ALL"}, "limit": limit, "last_id": last_id},
            )
            items = body.get("result", {}).get("items") or body.get("items") or []
            for it in items:
                yield it
            last_id = body.get("result", {}).get("last_id") or body.get("last_id") or ""
            if not last_id or not items:
                break

    def _as_id_list(self, ids: Iterable[int | str]) -> list[int]:
        out: list[int] = []
        for i in ids:
            try:
                out.append(int(i))
            except (TypeError, ValueError):
                continue
        if not out:
            raise ValueError("at least one valid product id is required")
        return out

    def get_product_info(self, ids: Iterable[int | str]) -> dict[str, Any]:
        """/v3/product/info/list -> product info (price, stock, status...)."""
        pid = self._as_id_list(ids)
        return self._post("/v3/product/info/list", {"product_id": pid})

    def get_product_attributes(self, ids: Iterable[int | str]) -> dict[str, Any]:
        """/v4/product/info/attributes -> category, attributes, images (v4 = working version)."""
        pid = self._as_id_list(ids)
        return self._post(
            "/v4/product/info/attributes",
            {"filter": {"product_id": pid, "visibility": "ALL"}, "limit": 1000},
        )

    def get_product_images(self, ids: Iterable[int | str]) -> dict[str, Any]:
        """/v3/product/info/images -> image lists per product."""
        pid = self._as_id_list(ids)
        return self._post(
            "/v3/product/info/images",
            {"filter": {"product_id": pid, "visibility": "ALL"}, "limit": len(pid)},
        )

    def get_prices(self, ids: Iterable[int | str]) -> dict[str, Any]:
        """/v3/product/info/list -> price per product (v4/prices 404s on this account)."""
        pid = self._as_id_list(ids)
        return self._post(
            "/v3/product/info/list",
            {"product_id": pid, "sku": [], "offer_id": []},
        )
