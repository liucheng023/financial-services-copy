"""Centralized typed settings for the FinAgentOS backend.

Required env vars fail fast at import time when ``get_settings()`` is called.
Secret-bearing fields use ``pydantic.SecretStr`` so their plaintext value
never appears in ``repr()``, log output, or pydantic ``ValidationError``
messages — only the literal string ``"**********"`` does.

Env-var lifecycle contract (see backend/AGENTS.md "Configuration"):
  * Runtime required: SUPABASE_URL, SUPABASE_SERVICE_KEY, INTERNAL_ADMIN_TOKEN
  * Importer-only required: UPSTREAM_PLUGINS_PATH (read by
    ``app/importers/_cli_common.py`` via ``os.environ``, not by Settings).
  * Migration-only required: SUPABASE_DB_URL (consumed by psql / supabase-cli).
    Exposed here as an optional SecretStr so tooling that imports Settings
    can read it without leaking the embedded DB password.
  * Legacy optional: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL. Task 8 moved
    the LLM endpoint source of truth to the ``model_configs`` table; the
    FastAPI runtime no longer reads these.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import Field, SecretStr, ValidationError
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
    INTERNAL_ADMIN_TOKEN: SecretStr = Field(min_length=1)

    # Legacy optional. Phase 1 originally read the LLM endpoint from these env
    # vars; Task 8 moved the source of truth to the ``model_configs`` Supabase
    # table (selected via ``is_default``). Kept as optional to avoid breaking
    # existing local ``.env`` files and to allow scripts that probe the LLM
    # outside the request lifecycle. Nothing in the FastAPI runtime reads them.
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: SecretStr | None = None
    LLM_MODEL: str | None = None

    # Optional. Postgres connection string used by migration / direct-SQL tooling
    # (psql, supabase-cli). The FastAPI runtime never reads it — it talks PostgREST
    # via SUPABASE_URL + SUPABASE_SERVICE_KEY. Kept as SecretStr because the URL
    # carries the database password.
    SUPABASE_DB_URL: SecretStr | None = None

    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


# Pydantic v2 ValidationError messages embed ``input_value=<raw dict>`` which,
# for ``BaseSettings``, is the raw env-source dict. That dict contains
# plaintext values for SecretStr-typed fields (SecretStr coercion happens
# AFTER input collection), so the formatted error can leak credentials —
# even with truncation, short secrets fit within the visible window.
# Strip the ``input_value=...`` clause before re-raising.
_INPUT_VALUE_RE = re.compile(r", input_value=.*?, input_type=[A-Za-z_]+")


class SettingsValidationError(RuntimeError):
    """Re-raised in place of pydantic ValidationError with input_value scrubbed."""


def _build_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        sanitized = _INPUT_VALUE_RE.sub("", str(exc))
        raise SettingsValidationError(sanitized) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _build_settings()


def reset_settings_cache() -> None:
    """Test-only helper: clear the cached Settings instance."""
    get_settings.cache_clear()
