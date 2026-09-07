"""Environment-based configuration for local and Azure execution."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Expected a boolean value, received: {value!r}")


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings. Secrets are read from environment variables only."""

    use_api: bool = False
    sqlite_path: Path = PROJECT_ROOT / "data" / "sample.db"
    db_api_base_url: str = "http://127.0.0.1:8000"
    db_api_key: str = ""
    mcp_api_key: str = ""
    host: str = "127.0.0.1"
    port: int = 8000
    request_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        running_in_azure = bool(env.get("WEBSITE_INSTANCE_ID"))

        default_sqlite_path = (
            Path(tempfile.gettempdir()) / "azure_mcp.db"
            if running_in_azure
            else PROJECT_ROOT / "data" / "sample.db"
        )
        sqlite_path = Path(env.get("SQLITE_PATH", str(default_sqlite_path)))
        if not sqlite_path.is_absolute():
            sqlite_path = PROJECT_ROOT / sqlite_path

        default_host = "0.0.0.0" if running_in_azure else "127.0.0.1"
        return cls(
            use_api=_as_bool(env.get("USE_API"), default=False),
            sqlite_path=sqlite_path,
            db_api_base_url=env.get("DB_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            db_api_key=env.get("DB_API_KEY", ""),
            mcp_api_key=env.get("MCP_API_KEY", ""),
            host=env.get("MCP_HOST", default_host),
            port=int(env.get("MCP_PORT", "8000")),
            request_timeout_seconds=float(env.get("DB_API_TIMEOUT_SECONDS", "10")),
        )
