from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.importers.agent_parser import (
    AgentParseError,
    discover_agent_files,
    parse_agent_file,
)
from app.importers.import_agents import (
    UPSTREAM_ENV_VAR,
    MissingUpstreamPathError,
    _resolve_upstream_root,
    main,
)


def test_parse_pitch_agent_from_upstream(upstream_plugins_root: Path) -> None:
    pitch_md = upstream_plugins_root / "agent-plugins" / "pitch-agent" / "agents" / "pitch-agent.md"
    plugin_json = (
        upstream_plugins_root / "agent-plugins" / "pitch-agent" / ".claude-plugin" / "plugin.json"
    )
    if not pitch_md.is_file() or not plugin_json.is_file():
        pytest.skip("pitch-agent files not present in this upstream copy")

    agent = parse_agent_file(pitch_md, plugin_json)

    assert agent.slug == "pitch-agent"
    assert "Pitch Agent" in agent.name or agent.name == "pitch-agent"
    assert agent.description and "pitch" in agent.description.lower()
    assert agent.system_prompt.startswith("You are the Pitch Agent")
    assert agent.workflow is not None and "Scope the ask" in agent.workflow
    assert agent.guardrails is not None and "Cite every number" in agent.guardrails
    assert agent.outputs is not None and "Excel valuation workbook" in agent.outputs
    assert agent.raw_frontmatter["name"] == "pitch-agent"
    assert agent.plugin_metadata["name"] == "pitch-agent"
    assert agent.source_path.endswith("pitch-agent.md")


def test_parser_does_not_modify_upstream_files(
    upstream_plugins_root: Path, tmp_path: Path
) -> None:
    pairs = discover_agent_files(upstream_plugins_root)
    assert pairs, "expected at least one agent-plugin in upstream copy"

    mtimes_before = {p[0]: p[0].stat().st_mtime_ns for p in pairs[:3]}
    modes_before = {p[0]: stat.S_IMODE(p[0].stat().st_mode) for p in pairs[:3]}

    for md_path, plugin_json in pairs[:3]:
        parse_agent_file(md_path, plugin_json)

    for path, mtime in mtimes_before.items():
        assert path.stat().st_mtime_ns == mtime, f"parser modified {path}"
        assert stat.S_IMODE(path.stat().st_mode) == modes_before[path]


def test_discover_returns_ten_agents(upstream_plugins_root: Path) -> None:
    pairs = discover_agent_files(upstream_plugins_root)
    slugs = {p[0].stem for p in pairs}
    assert len(slugs) >= 10, f"expected >=10 agents, found {len(slugs)}: {slugs}"
    assert "pitch-agent" in slugs
    assert "market-researcher" in slugs


def test_missing_upstream_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(UPSTREAM_ENV_VAR, raising=False)
    with pytest.raises(MissingUpstreamPathError) as exc_info:
        _resolve_upstream_root()
    assert UPSTREAM_ENV_VAR in str(exc_info.value)


def test_missing_upstream_env_cli_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(UPSTREAM_ENV_VAR, raising=False)
    rc = main([])
    assert rc == 2
    captured = capsys.readouterr()
    assert UPSTREAM_ENV_VAR in captured.err


def test_apply_without_supabase_env_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    upstream_plugins_root: Path,
) -> None:
    monkeypatch.setenv(UPSTREAM_ENV_VAR, str(upstream_plugins_root))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    rc = main(["--apply"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "SUPABASE_URL" in captured.err and "SUPABASE_SERVICE_KEY" in captured.err


def test_dry_run_cli_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    upstream_plugins_root: Path,
) -> None:
    monkeypatch.setenv(UPSTREAM_ENV_VAR, str(upstream_plugins_root))
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert '"upstream_root"' in captured.out
    assert '"slug": "pitch-agent"' in captured.out


def test_parse_rejects_missing_frontmatter(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text("no frontmatter here\n", encoding="utf-8")
    plugin = tmp_path / "plugin.json"
    plugin.write_text("{}", encoding="utf-8")
    with pytest.raises(AgentParseError):
        parse_agent_file(md, plugin)


def test_parse_rejects_missing_name(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text("---\ndescription: hi\n---\n\nbody\n", encoding="utf-8")
    plugin = tmp_path / "plugin.json"
    plugin.write_text("{}", encoding="utf-8")
    with pytest.raises(AgentParseError):
        parse_agent_file(md, plugin)
