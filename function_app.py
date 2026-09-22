"""Azure Functions Python v2 entry point."""

import asyncio
from datetime import datetime, timezone
import json
import os
import secrets
import time
from urllib.parse import urlsplit

import azure.functions as func
from fastapi import Header
from fastapi.responses import JSONResponse
import httpx

from app.runtime import asgi_app


# Application-level API keys are enforced by the ASGI app. Anonymous here keeps
# the public endpoint compatible with remote MCP clients using X-API-Key.
app = func.AsgiFunctionApp(
    app=asgi_app,
    http_auth_level=func.AuthLevel.ANONYMOUS,
    function_name="azure_mcp",
)


# Temporary, X-API-Key-protected outbound connectivity diagnostic.
# Disabled until OUTBOUND_PROBE_URLS is set to a JSON array of 1-3 approved
# HTTPS URLs in Azure app settings. It never accepts target URLs from callers,
# sends credentials, follows redirects, or reads/returns response bodies.
def _outbound_probe_urls(raw: str) -> list[str]:
    urls = json.loads(raw)
    if not isinstance(urls, list) or not 1 <= len(urls) <= 3:
        raise ValueError("Configure one to three approved HTTPS URLs.")
    for url in urls:
        if not isinstance(url, str) or len(url) > 2048:
            raise ValueError("Invalid probe URL.")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.query
            or parsed.fragment
            or any(ord(char) <= 32 for char in url)
        ):
            raise ValueError("Only HTTPS URLs without credentials or queries are allowed.")
    return urls


async def _probe_one(client: httpx.AsyncClient, url: str) -> dict:
    started = time.monotonic()
    result = {"url": url, "method": "GET", "http_status": None}

    async def read_headers() -> None:
        async with client.stream("GET", url) as response:
            result.update(
                http_status=response.status_code,
                reason=response.reason_phrase,
                outcome="http_response",
            )

    try:
        await asyncio.wait_for(read_headers(), timeout=15)
    except (asyncio.TimeoutError, httpx.TimeoutException):
        result.update(outcome="timeout", error_type="Timeout")
    except httpx.RequestError as exc:
        result.update(outcome="request_failed", error_type=type(exc).__name__)
    result["duration_ms"] = round((time.monotonic() - started) * 1000)
    return result


@asgi_app.post("/diagnostics/outbound", include_in_schema=False)
async def outbound_connectivity_probe(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> JSONResponse:
    expected_api_key = os.environ.get("MCP_API_KEY", "")
    if (
        not expected_api_key
        or not x_api_key
        or not secrets.compare_digest(x_api_key, expected_api_key)
    ):
        return JSONResponse(
            {"error": "Unauthorized."},
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )

    raw = os.environ.get("OUTBOUND_PROBE_URLS", "")
    if not raw:
        return JSONResponse(
            {"error": "Probe disabled: OUTBOUND_PROBE_URLS is not configured."},
            status_code=409,
            headers={"Cache-Control": "no-store"},
        )
    try:
        urls = _outbound_probe_urls(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JSONResponse(
            {"error": "Invalid OUTBOUND_PROBE_URLS configuration."},
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "azure-mcp-connectivity-probe/1.0"},
    ) as client:
        results = await asyncio.gather(*(_probe_one(client, url) for url in urls))

    return JSONResponse(
        {
            "source": "function_runtime",
            "azure_site": os.environ.get("WEBSITE_SITE_NAME"),
            "utc": datetime.now(timezone.utc).isoformat(),
            "results": results,
        },
        headers={"Cache-Control": "no-store"},
    )


# build_asgi_app mounts the MCP transport at "/" as the final fallback route.
# This diagnostic is registered afterward, so move only its route ahead of the
# mount to ensure /diagnostics/outbound reaches the protected handler.
asgi_app.router.routes.insert(0, asgi_app.router.routes.pop())
