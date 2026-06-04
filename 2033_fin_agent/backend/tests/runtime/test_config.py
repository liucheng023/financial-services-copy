from __future__ import annotations

import pytest


def test_settings_load_from_env(env_setup) -> None:
    from app.core.config import Settings, get_settings

    s = get_settings()
    assert isinstance(s, Settings)
    assert s.SUPABASE_URL == "https://example.supabase.co"
    assert s.LLM_MODEL == "glm-5-test"
    assert s.LOG_LEVEL == "INFO"
    assert s.cors_origin_list() == ["http://localhost:3000"]


def test_missing_required_env_raises_clear_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings, reset_settings_cache

    reset_settings_cache()
    for k in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "UPSTREAM_PLUGINS_PATH",
        "INTERNAL_ADMIN_TOKEN",
    ):
        monkeypatch.delenv(k, raising=False)

    with pytest.raises(Exception) as ei:
        Settings()  # type: ignore[call-arg]
    msg = str(ei.value)
    assert "SUPABASE_URL" in msg
    assert "LLM_API_KEY" in msg


def test_secret_str_does_not_leak_in_repr_or_str(env_setup) -> None:
    from app.core.config import get_settings

    s = get_settings()
    plaintext_admin = "admin-token-test-value"
    plaintext_llm = "llm-key-test-value"
    plaintext_supabase = "service-key-test-value"

    assert plaintext_admin not in repr(s)
    assert plaintext_admin not in str(s)
    assert plaintext_llm not in repr(s)
    assert plaintext_llm not in str(s)
    assert plaintext_supabase not in repr(s)
    assert plaintext_supabase not in str(s)

    assert s.INTERNAL_ADMIN_TOKEN.get_secret_value() == plaintext_admin
    assert s.LLM_API_KEY.get_secret_value() == plaintext_llm
    assert s.SUPABASE_SERVICE_KEY.get_secret_value() == plaintext_supabase


def test_secret_str_not_in_validation_error_when_one_field_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings, reset_settings_cache

    reset_settings_cache()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "non-leaky-secret-zzz")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.llm/v1")
    monkeypatch.setenv("LLM_API_KEY", "non-leaky-secret-zzz")
    monkeypatch.setenv("LLM_MODEL", "glm-5-test")
    monkeypatch.setenv("UPSTREAM_PLUGINS_PATH", "/tmp/u")
    monkeypatch.delenv("INTERNAL_ADMIN_TOKEN", raising=False)

    with pytest.raises(Exception) as ei:
        Settings()  # type: ignore[call-arg]
    assert "non-leaky-secret-zzz" not in str(ei.value)


def test_supabase_db_url_is_optional_and_absent_by_default(env_setup) -> None:
    from app.core.config import get_settings

    s = get_settings()
    assert s.SUPABASE_DB_URL is None


def test_supabase_db_url_is_secret_when_set(env_setup_with_db_url) -> None:
    from app.core.config import get_settings

    db_url = env_setup_with_db_url
    s = get_settings()
    assert s.SUPABASE_DB_URL is not None
    assert s.SUPABASE_DB_URL.get_secret_value() == db_url
    assert "db-url-secret-zzz" not in repr(s)
    assert "db-url-secret-zzz" not in str(s)
