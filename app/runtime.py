"""Module-level application used by Uvicorn and Azure Functions."""

from app.asgi import build_asgi_app
from app.config import Settings


settings = Settings.from_env()
asgi_app = build_asgi_app(settings)

