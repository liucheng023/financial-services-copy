"""Centralized typed settings for the FinAgentOS backend.

Required env vars fail fast at import time when ``get_settings()`` is called.
Secret-bearing fields use ``pydantic.SecretStr`` so their plaintext value
never appears in ``repr()``, log output, or pydantic ``ValidationError``
messages — only the literal string ``"**********"`` does.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    SUPABASE_URL: str = Field(min_length=1)
    SUPABASE_SERVICE_KEY: SecretStr = Field(min_length=1)
    LLM_BASE_URL: str = Field(min_length=1)
    LLM_API_KEY: SecretStr = Field(min_length=1)
    LLM_MODEL: str = Field(min_length=1)
    UPSTREAM_PLUGINS_PATH: str = Field(min_length=1)
    INTERNAL_ADMIN_TOKEN: SecretStr = Field(min_length=1)

    # Optional. Postgres connection string used by migration / direct-SQL tooling
    # (psql, supabase-cli). The FastAPI runtime never reads it — it talks PostgREST
    # via SUPABASE_URL + SUPABASE_SERVICE_KEY. Kept as SecretStr because the URL
    # carries the database password.
    SUPABASE_DB_URL: SecretStr | None = None

    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Test-only helper: clear the cached Settings instance."""
    get_settings.cache_clear()
