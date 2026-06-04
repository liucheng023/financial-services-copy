from __future__ import annotations

import pytest


def test_smoke_supabase_missing_env_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import smoke_supabase

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    rc = smoke_supabase.main([])
    assert rc == 2
    captured = capsys.readouterr()
    assert "SUPABASE_URL" in captured.err
    assert "SUPABASE_SERVICE_KEY" in captured.err


def test_smoke_supabase_partial_env_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import smoke_supabase

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    rc = smoke_supabase.main([])
    assert rc == 2
    captured = capsys.readouterr()
    assert "SUPABASE_SERVICE_KEY" in captured.err
    assert "SUPABASE_URL" not in captured.err


def test_smoke_supabase_expected_tables_match_migration() -> None:
    from scripts import smoke_supabase

    assert "agents" in smoke_supabase.EXPECTED_TABLES
    assert "chat_sessions" in smoke_supabase.EXPECTED_TABLES
    assert "mcp_servers" in smoke_supabase.EXPECTED_TABLES
    assert len(smoke_supabase.EXPECTED_TABLES) == 11
