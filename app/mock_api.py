"""Replaceable sample DB API contract backed by a customer repository."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from app.database import CustomerRepository
from app.errors import NotFoundError


def create_mock_api(repository: CustomerRepository, api_key: str = "") -> FastAPI:
    """Create the sample DB API over the selected repository.

    Local development may use an empty key. Azure startup validation requires a
    strong DB_API_KEY, so deployed API routes always remain authenticated.
    """

    api = FastAPI(
        title="Azure Sample DB API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if api_key and (not x_api_key or not secrets.compare_digest(x_api_key, api_key)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid DB API key",
            )

    auth = Depends(verify_api_key)

    @api.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "azure-mcp"}

    @api.get("/api/customers", dependencies=[auth], tags=["customers"])
    def search_customers(
        name: str | None = Query(default=None),
        country: str | None = Query(default=None),
        tier: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        return repository.search_customers(name=name, country=country, tier=tier)

    @api.get(
        "/api/customers/{customer_id}/sales-summary",
        dependencies=[auth],
        tags=["customers"],
    )
    def get_sales_summary(customer_id: int) -> dict[str, Any]:
        try:
            return repository.get_sales_summary(customer_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.get("/api/customers/{customer_id}", dependencies=[auth], tags=["customers"])
    def get_customer(customer_id: int) -> dict[str, Any]:
        try:
            return repository.get_customer(customer_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.get("/api/orders", dependencies=[auth], tags=["orders"])
    def list_orders(
        customer_id: int | None = Query(default=None),
        order_status: str | None = Query(default=None, alias="status"),
    ) -> list[dict[str, Any]]:
        return repository.list_orders(customer_id=customer_id, status=order_status)

    return api
