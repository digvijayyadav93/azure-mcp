"""Composition root for the database API and MCP Streamable HTTP application."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from fastapi import FastAPI

from app.backends import CustomerBackend, build_backend
from app.config import Settings
from app.database import AzureSQLRepository, CustomerRepository, SQLiteRepository
from app.mcp_server import create_mcp_server
from app.mock_api import create_mock_api


ASGIApp = Callable[
    [dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]],
    Awaitable[None],
]


class MCPApiKeyMiddleware:
    """Pure ASGI middleware protecting only /mcp with X-API-Key."""

    def __init__(self, app: ASGIApp, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        path = scope.get("path", "")
        is_mcp_request = path == "/mcp" or path.startswith("/mcp/")
        if scope.get("type") == "http" and is_mcp_request and self.api_key:
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            supplied_key = headers.get("x-api-key", "")
            if not supplied_key or not secrets.compare_digest(supplied_key, self.api_key):
                body = b'{"error":"Missing or invalid MCP API key"}'
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("ascii")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def build_asgi_app(
    settings: Settings,
    repository: CustomerRepository | None = None,
    backend: CustomerBackend | None = None,
) -> FastAPI:
    if repository is None:
        repository = (
            AzureSQLRepository(settings.sql_connection_string)
            if settings.sql_connection_string
            else SQLiteRepository(settings.sqlite_path)
        )
    repository.initialize()
    backend = backend or build_backend(settings, repository)

    mcp_server = create_mcp_server(backend)
    mcp_asgi = mcp_server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        host=settings.host,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async with mcp_asgi.router.lifespan_context(mcp_asgi):
            yield

    api = create_mock_api(repository, api_key=settings.db_api_key)
    api.router.lifespan_context = lifespan
    api.state.settings = settings
    api.state.repository = repository
    api.state.backend = backend
    api.state.mcp_server = mcp_server
    api.mount("/", MCPApiKeyMiddleware(mcp_asgi, settings.mcp_api_key))
    return api
