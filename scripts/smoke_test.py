"""Exercise a running MCP server without Postman or Node.js.

Example:
    python scripts/smoke_test.py --url http://127.0.0.1:8000/mcp \
        --api-key temporary-test-key
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def post_jsonrpc(
    client: httpx.Client,
    url: str,
    request_id: int,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    response = client.post(url, json=payload)
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(json.dumps(body["error"], indent=2))
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify MCP discovery and a tool call")
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--api-key", default="temporary-test-key")
    parser.add_argument("--customer-id", type=int, default=1)
    args = parser.parse_args()

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "X-API-Key": args.api_key,
    }
    with httpx.Client(headers=headers, timeout=20) as client:
        initialize = post_jsonrpc(
            client,
            args.url,
            1,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "azure-mcp-smoke-test", "version": "1.0.0"},
            },
        )
        listed = post_jsonrpc(client, args.url, 2, "tools/list", {})
        called = post_jsonrpc(
            client,
            args.url,
            3,
            "tools/call",
            {"name": "get_customer", "arguments": {"customer_id": args.customer_id}},
        )

    tool_names = [tool["name"] for tool in listed["result"]["tools"]]
    print("MCP server:", initialize["result"]["serverInfo"]["name"])
    print("Registered tools:", ", ".join(tool_names))
    print("get_customer result:")
    print(json.dumps(called["result"], indent=2))


if __name__ == "__main__":
    main()
