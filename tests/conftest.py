from pathlib import Path

import pytest

from app.config import Settings
from app.database import SQLiteRepository


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        use_api=False,
        sqlite_path=tmp_path / "test.db",
        db_api_base_url="http://db-api.test",
        db_api_key="db-test-key",
        mcp_api_key="mcp-test-key",
        host="testserver",
        port=8000,
        request_timeout_seconds=2,
    )


@pytest.fixture
def repository(settings: Settings) -> SQLiteRepository:
    repo = SQLiteRepository(settings.sqlite_path)
    repo.initialize()
    return repo

