"""Backend abstractions for direct database and HTTP API execution."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.config import Settings
from app.database import CustomerRepository
from app.errors import BackendError, NotFoundError


class CustomerBackend(Protocol):
    def get_customer(self, customer_id: int) -> dict[str, Any]: ...

    def search_customers(
        self,
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_orders(
        self,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_sales_summary(self, customer_id: int) -> dict[str, Any]: ...


class SQLiteBackend:
    """Direct repository backend used for SQLite or Azure SQL."""

    def __init__(self, repository: CustomerRepository):
        self.repository = repository

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        return self.repository.get_customer(customer_id)

    def search_customers(
        self,
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.repository.search_customers(name=name, country=country, tier=tier)

    def list_orders(
        self,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.repository.list_orders(customer_id=customer_id, status=status)

    def get_sales_summary(self, customer_id: int) -> dict[str, Any]:
        return self.repository.get_sales_summary(customer_id)


class APIBackend:
    """HTTP adapter used for the sample API now and a production DB API later."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise BackendError(f"DB API request failed: {exc}") from exc

        if response.status_code == 404:
            detail = response.json().get("detail", "Record was not found")
            raise NotFoundError(str(detail))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendError(
                f"DB API returned HTTP {response.status_code}: {response.text[:300]}"
            ) from exc
        return response.json()

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        return self._get(f"/api/customers/{customer_id}")

    def search_customers(
        self,
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            key: value
            for key, value in {"name": name, "country": country, "tier": tier}.items()
            if value
        }
        return self._get("/api/customers", params=params)

    def list_orders(
        self,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if customer_id is not None:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status
        return self._get("/api/orders", params=params)

    def get_sales_summary(self, customer_id: int) -> dict[str, Any]:
        return self._get(f"/api/customers/{customer_id}/sales-summary")


def build_backend(
    settings: Settings,
    repository: CustomerRepository,
) -> CustomerBackend:
    if settings.use_api:
        return APIBackend(
            base_url=settings.db_api_base_url,
            api_key=settings.db_api_key,
            timeout_seconds=settings.request_timeout_seconds,
        )
    return SQLiteBackend(repository)
