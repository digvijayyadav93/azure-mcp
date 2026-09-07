from pathlib import Path

import pytest

from app.config import Settings


def test_use_api_switch_reads_true() -> None:
    settings = Settings.from_env(
        {
            "USE_API": "true",
            "SQLITE_PATH": "data/test-config.db",
            "MCP_PORT": "9000",
        }
    )
    assert settings.use_api is True
    assert settings.port == 9000
    assert settings.sqlite_path == Path(__file__).resolve().parents[1] / "data" / "test-config.db"


def test_invalid_boolean_is_rejected() -> None:
    with pytest.raises(ValueError, match="boolean"):
        Settings.from_env({"USE_API": "perhaps"})

