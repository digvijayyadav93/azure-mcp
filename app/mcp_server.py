"""MCP tool registration. This file is the tool registry."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from app.backends import CustomerBackend


def create_mcp_server(backend: CustomerBackend) -> MCPServer:
    server = MCPServer(
        name="azure-customer-data",
        title="Azure Customer Data MCP",
        description="Read-only customer and order tools for a customer-data agent.",
        instructions=(
            "Use these read-only tools to find customers, inspect their orders, "
            "and calculate customer sales summaries."
        ),
        version="1.0.0",
    )

    @server.tool()
    def get_customer(customer_id: int) -> dict[str, Any]:
        """Get one customer by numeric customer ID."""
        return backend.get_customer(customer_id)

    @server.tool()
    def search_customers(
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search customers by optional name, country, and membership tier."""
        return backend.search_customers(name=name, country=country, tier=tier)

    @server.tool()
    def list_orders(
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List orders, optionally filtered by customer ID and order status."""
        return backend.list_orders(customer_id=customer_id, status=status)

    @server.tool()
    def get_sales_summary(customer_id: int) -> dict[str, Any]:
        """Return order count, total sales, and average order value for a customer."""
        return backend.get_sales_summary(customer_id)

    return server
