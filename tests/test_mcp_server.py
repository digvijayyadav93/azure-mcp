import pytest

from app.backends import SQLiteBackend
from app.database import SQLiteRepository
from app.mcp_server import create_mcp_server


@pytest.mark.asyncio
async def test_registry_contains_all_four_tools(repository: SQLiteRepository) -> None:
    server = create_mcp_server(SQLiteBackend(repository))
    tools = await server.list_tools()
    assert {tool.name for tool in tools} == {
        "get_customer",
        "search_customers",
        "list_orders",
        "get_sales_summary",
    }


@pytest.mark.asyncio
async def test_registered_tool_call_returns_structured_data(repository: SQLiteRepository) -> None:
    server = create_mcp_server(SQLiteBackend(repository))
    result = await server.call_tool("get_customer", {"customer_id": 1})
    assert result.structured_content["id"] == 1
    assert result.structured_content["name"] == "Aarav Sharma"

