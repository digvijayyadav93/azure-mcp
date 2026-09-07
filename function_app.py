"""Azure Functions Python v2 entry point."""

import azure.functions as func

from app.runtime import asgi_app


# Application-level API keys are enforced by the ASGI app. Anonymous here keeps
# the public endpoint compatible with remote MCP clients using X-API-Key.
app = func.AsgiFunctionApp(
    app=asgi_app,
    http_auth_level=func.AuthLevel.ANONYMOUS,
    function_name="azure_mcp",
)
