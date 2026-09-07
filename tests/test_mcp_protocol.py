from typing import Any

import httpx
import pytest

from app.asgi import build_asgi_app
from app.config import Settings
from app.database import SQLiteRepository


def rpc(method: str, request_id: int, params: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


@pytest.mark.asyncio
async def test_streamable_http_discovery_and_call(settings: Settings) -> None:
    app = build_asgi_app(settings)
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "X-API-Key": settings.mcp_api_key,
    }

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unauthorized = await client.post("/mcp", json=rpc("tools/list", 1, {}))
            assert unauthorized.status_code == 401

            initialize = await client.post(
                "/mcp",
                headers=headers,
                json=rpc(
                    "initialize",
                    2,
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "1.0.0"},
                    },
                ),
            )
            assert initialize.status_code == 200
            assert initialize.json()["result"]["serverInfo"]["name"] == "azure-customer-data"

            listed = await client.post("/mcp", headers=headers, json=rpc("tools/list", 3, {}))
            assert listed.status_code == 200
            names = {tool["name"] for tool in listed.json()["result"]["tools"]}
            assert names == {
                "get_customer",
                "search_customers",
                "list_orders",
                "get_sales_summary",
            }

            called = await client.post(
                "/mcp",
                headers=headers,
                json=rpc(
                    "tools/call",
                    4,
                    {"name": "get_customer", "arguments": {"customer_id": 1}},
                ),
            )
            assert called.status_code == 200
            assert called.json()["result"]["structuredContent"]["name"] == "Aarav Sharma"
