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
        name: str = "",
        country: str = "",
        tier: str = "",
    ) -> list[dict[str, Any]]:
        """Search customers. Use an empty string for filters that are not needed."""
        return backend.search_customers(
            name=name or None,
            country=country or None,
            tier=tier or None,
        )

    @server.tool()
    def list_orders(
        customer_id: int = 0,
        status: str = "",
    ) -> list[dict[str, Any]]:
        """List orders. Use customer ID 0 and empty status for all orders."""
        return backend.list_orders(
            customer_id=customer_id or None,
            status=status or None,
        )

    @server.tool()
    def get_sales_summary(customer_id: int) -> dict[str, Any]:
        """Return order count, total sales, and average order value for a customer."""
        return backend.get_sales_summary(customer_id)

    return server
