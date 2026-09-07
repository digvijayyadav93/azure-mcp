import json

import httpx
import pytest

from app.backends import APIBackend, SQLiteBackend, build_backend
from app.config import Settings
from app.database import SQLiteRepository
from app.errors import NotFoundError


def test_build_backend_obeys_use_api(settings: Settings, repository: SQLiteRepository) -> None:
    assert isinstance(build_backend(settings, repository), SQLiteBackend)
    api_settings = Settings(
        use_api=True,
        sqlite_path=settings.sqlite_path,
        db_api_base_url="http://db-api.test",
        db_api_key="db-key",
    )
    assert isinstance(build_backend(api_settings, repository), APIBackend)


def test_api_backend_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "db-key"
        if request.url.path == "/api/customers/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "Aarav Sharma",
                    "email": "aarav.sharma@example.com",
                    "country": "India",
                    "tier": "Gold",
                },
            )
        if request.url.path == "/api/customers/999":
            return httpx.Response(404, json={"detail": "Customer 999 was not found"})
        return httpx.Response(200, content=json.dumps([]), headers={"Content-Type": "application/json"})

    backend = APIBackend(
        "http://db-api.test",
        api_key="db-key",
        transport=httpx.MockTransport(handler),
    )
    assert backend.get_customer(1)["tier"] == "Gold"
    with pytest.raises(NotFoundError, match="999"):
        backend.get_customer(999)

