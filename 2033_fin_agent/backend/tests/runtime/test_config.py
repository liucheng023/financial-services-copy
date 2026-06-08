from __future__ import annotations

import pytest


def test_settings_load_from_env(env_setup) -> None:
    from app.core.config import Settings, get_settings

    s = get_settings()
    assert isinstance(s, Settings)
    assert s.SUPABASE_URL == "https://example.supabase.co"
    assert s.LOG_LEVEL == "INFO"
    assert s.cors_origin_list() == ["http://localhost:3000"]


def test_settings_load_without_legacy_llm_env(env_setup) -> None:
    from app.core.config import get_settings

    s = get_settings()
    assert s.LLM_BASE_URL is None
    assert s.LLM_API_KEY is None
    assert s.LLM_MODEL is None


def test_settings_load_without_upstream_plugins_path(env_setup) -> None:
    from app.core.config import Settings, get_settings

    s = get_settings()
    assert isinstance(s, Settings)
    assert not hasattr(s, "UPSTREAM_PLUGINS_PATH")


def test_missing_required_env_raises_clear_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import _build_settings, reset_settings_cache

    reset_settings_cache()
    for k in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "INTERNAL_ADMIN_TOKEN",
        "UPSTREAM_PLUGINS_PATH",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
    ):
        monkeypatch.delenv(k, raising=False)

    with pytest.raises(Exception) as ei:
        _build_settings()
    msg = str(ei.value)
    assert "SUPABASE_URL" in msg
    assert "INTERNAL_ADMIN_TOKEN" in msg
    assert "UPSTREAM_PLUGINS_PATH" not in msg
    assert "LLM_BASE_URL" not in msg
    assert "LLM_API_KEY" not in msg
    assert "LLM_MODEL" not in msg


def test_secret_str_does_not_leak_in_repr_or_str(env_setup) -> None:
    from app.core.config import get_settings

    s = get_settings()
    plaintext_admin = "admin-token-test-value"
    plaintext_supabase = "service-key-test-value"

    assert plaintext_admin not in repr(s)
    assert plaintext_admin not in str(s)
    assert plaintext_supabase not in repr(s)
    assert plaintext_supabase not in str(s)

    assert s.INTERNAL_ADMIN_TOKEN.get_secret_value() == plaintext_admin
    assert s.SUPABASE_SERVICE_KEY.get_secret_value() == plaintext_supabase


def test_llm_api_key_remains_secret_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings, reset_settings_cache

    reset_settings_cache()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "non-leaky-secret-aaa")
    monkeypatch.setenv("INTERNAL_ADMIN_TOKEN", "non-leaky-secret-bbb")
    monkeypatch.setenv("LLM_API_KEY", "llm-key-secret-ccc")

    s = get_settings()
    assert s.LLM_API_KEY is not None
    assert s.LLM_API_KEY.get_secret_value() == "llm-key-secret-ccc"
    assert "llm-key-secret-ccc" not in repr(s)
    assert "llm-key-secret-ccc" not in str(s)


def test_secret_str_not_in_validation_error_when_one_field_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import (
        SettingsValidationError,
        _build_settings,
        reset_settings_cache,
    )

    reset_settings_cache()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "non-leaky-secret-zzz")
    monkeypatch.delenv("UPSTREAM_PLUGINS_PATH", raising=False)
    monkeypatch.delenv("INTERNAL_ADMIN_TOKEN", raising=False)

    with pytest.raises(SettingsValidationError) as ei:
        _build_settings()
    err = str(ei.value)
    assert "INTERNAL_ADMIN_TOKEN" in err
    assert "non-leaky-secret-zzz" not in err
    assert "input_value" not in err


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
