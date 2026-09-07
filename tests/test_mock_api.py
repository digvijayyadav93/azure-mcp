import httpx
import pytest

from app.database import SQLiteRepository
from app.mock_api import create_mock_api


@pytest.mark.asyncio
async def test_mock_api_contract_and_auth(repository: SQLiteRepository) -> None:
    app = create_mock_api(repository, api_key="secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/api/customers/1")).status_code == 401

        headers = {"X-API-Key": "secret"}
        customer = await client.get("/api/customers/1", headers=headers)
        assert customer.status_code == 200
        assert customer.json()["name"] == "Aarav Sharma"

        customers = await client.get("/api/customers?tier=Gold", headers=headers)
        assert [item["id"] for item in customers.json()] == [1, 3]

        orders = await client.get("/api/orders?customer_id=1", headers=headers)
        assert len(orders.json()) == 2

        summary = await client.get("/api/customers/1/sales-summary", headers=headers)
        assert summary.json()["total_amount"] == 1700.5

        missing = await client.get("/api/customers/999", headers=headers)
        assert missing.status_code == 404

