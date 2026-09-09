"""Prove authentication, tool discovery, and a live MCP tool call.

Example:
    python scripts/smoke_test.py --url http://127.0.0.1:8000/mcp \
        --api-key temporary-test-key
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


EXPECTED_TOOLS = {
    "get_customer",
    "search_customers",
    "list_orders",
    "get_sales_summary",
}


def make_request(
    request_id: int,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def post_jsonrpc(
    client: httpx.Client,
    url: str,
    request_id: int,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.post(url, json=make_request(request_id, method, params))
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(json.dumps(body["error"], indent=2))
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify MCP auth, discovery, and data")
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--api-key", default="temporary-test-key")
    parser.add_argument("--customer-id", type=int, default=1)
    args = parser.parse_args()

    initialize_params = {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "azure-mcp-smoke-test", "version": "1.0.0"},
    }
    common_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    with httpx.Client(headers=common_headers, timeout=20) as unauthenticated:
        denied = unauthenticated.post(
            args.url,
            json=make_request(1, "initialize", initialize_params),
        )
    if denied.status_code != 401:
        raise RuntimeError(
            "MCP authentication is not enforced: unauthenticated request returned "
            f"HTTP {denied.status_code}, expected 401"
        )

    headers = {**common_headers, "X-API-Key": args.api_key}
    with httpx.Client(headers=headers, timeout=20) as client:
        initialize = post_jsonrpc(client, args.url, 2, "initialize", initialize_params)
        listed = post_jsonrpc(client, args.url, 3, "tools/list", {})
        called = post_jsonrpc(
            client,
            args.url,
            4,
            "tools/call",
            {"name": "get_customer", "arguments": {"customer_id": args.customer_id}},
        )

    tool_names = {tool["name"] for tool in listed["result"]["tools"]}
    if tool_names != EXPECTED_TOOLS:
        raise RuntimeError(
            f"Unexpected MCP tool registry: {sorted(tool_names)}; "
            f"expected {sorted(EXPECTED_TOOLS)}"
        )

    structured = called["result"].get("structuredContent", {})
    if structured.get("name") != "Aarav Sharma":
        raise RuntimeError(
            "get_customer did not return the expected database record: "
            f"{json.dumps(structured, default=str)}"
        )

    print("PASS: unauthenticated MCP request returned HTTP 401")
    print("PASS: MCP server", initialize["result"]["serverInfo"]["name"])
    print("PASS: exact tool registry", ", ".join(sorted(tool_names)))
    print("PASS: get_customer returned", json.dumps(structured, default=str))


if __name__ == "__main__":
    main()
