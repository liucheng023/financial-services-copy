from __future__ import annotations

from collections.abc import Iterator

import pytest

REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_KEY": "service-key-test-value",
    "LLM_BASE_URL": "https://example.llm/v1",
    "LLM_API_KEY": "llm-key-test-value",
    "LLM_MODEL": "glm-5-test",
    "UPSTREAM_PLUGINS_PATH": "/tmp/upstream-not-used-in-runtime-tests",
    "INTERNAL_ADMIN_TOKEN": "admin-token-test-value",
}


@pytest.fixture
def env_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    for k, v in REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    yield
    reset_settings_cache()


@pytest.fixture
def env_setup_with_db_url(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    for k, v in REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)
    db_url = "postgresql://postgres:db-url-secret-zzz@db.example.supabase.co:5432/postgres"
    monkeypatch.setenv("SUPABASE_DB_URL", db_url)
    yield db_url
    reset_settings_cache()
