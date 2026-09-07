"""Run the complete API + MCP stack locally."""

import uvicorn

from app.runtime import asgi_app, settings


if __name__ == "__main__":
    uvicorn.run(asgi_app, host=settings.host, port=settings.port)

