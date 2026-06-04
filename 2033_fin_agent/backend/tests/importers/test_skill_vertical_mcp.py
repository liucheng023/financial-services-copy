from __future__ import annotations

import stat
from pathlib import Path

import pytest

from app.importers._cli_common import UPSTREAM_ENV_VAR
from app.importers.agent_parser import discover_agent_files, parse_agent_file
from app.importers.associations import (
    derive_agent_mcp_candidates,
    derive_vertical_mcp_associations,
    derive_vertical_skill_associations,
)
from app.importers.import_all import main as import_all_main
from app.importers.import_mcps import main as import_mcps_main
from app.importers.import_skills import main as import_skills_main
from app.importers.import_verticals import main as import_verticals_main
from app.importers.mcp_parser import (
    collect_all_mcp_servers,
    discover_mcp_json_files,
    parse_mcp_json,
)
from app.importers.skill_parser import (
    SkillParseError,
    discover_skill_files,
    parse_skill_file,
)
from app.importers.vertical_parser import (
    VerticalParseError,
    discover_vertical_plugins,
    parse_vertical_plugin,
)

EXPECTED_VERTICALS = {
    "equity-research",
    "financial-analysis",
    "fund-admin",
    "investment-banking",
    "operations",
    "private-equity",
    "wealth-management",
}

EXPECTED_MCP_SLUGS = {
    "daloopa",
    "morningstar",
    "sp-global",
    "factset",
    "moodys",
    "mtnewswire",
    "aiera",
    "lseg",
    "pitchbook",
    "chronograph",
    "egnyte",
}


def test_discover_seven_verticals(upstream_plugins_root: Path) -> None:
    pairs = discover_vertical_plugins(upstream_plugins_root)
    slugs = {slug for _, slug in pairs}
    assert slugs == EXPECTED_VERTICALS, f"expected 7 verticals, got {slugs}"


def test_parse_financial_analysis_vertical(upstream_plugins_root: Path) -> None:
    pj = (
        upstream_plugins_root
        / "vertical-plugins"
        / "financial-analysis"
        / ".claude-plugin"
        / "plugin.json"
    )
    v = parse_vertical_plugin(pj, "financial-analysis")
    assert v.slug == "financial-analysis"
    assert v.name == "financial-analysis"
    assert v.description and "financial modeling" in v.description.lower()
    assert v.raw_manifest["version"]


def test_discover_at_least_50_skills(upstream_plugins_root: Path) -> None:
    pairs = discover_skill_files(upstream_plugins_root)
    assert len(pairs) >= 50, f"expected >=50 skills, found {len(pairs)}"


def test_parse_comps_analysis_skill(upstream_plugins_root: Path) -> None:
    skill_md = (
        upstream_plugins_root
        / "vertical-plugins"
        / "financial-analysis"
        / "skills"
        / "comps-analysis"
        / "SKILL.md"
    )
    if not skill_md.is_file():
        pytest.skip("comps-analysis SKILL.md not present in upstream copy")
    s = parse_skill_file(skill_md, "financial-analysis")
    assert s.slug == "comps-analysis"
    assert s.vertical_slug == "financial-analysis"
    assert "Comparable Company Analysis" in s.content
    assert len(s.content) > 200
    assert s.description and "comparable company" in s.description.lower()


def test_discover_eleven_mcp_servers(upstream_plugins_root: Path) -> None:
    servers = collect_all_mcp_servers(upstream_plugins_root)
    slugs = {s.slug for s in servers}
    assert slugs == EXPECTED_MCP_SLUGS, (
        f"expected 11 MCP slugs {EXPECTED_MCP_SLUGS}, got {len(slugs)}: {slugs}"
    )


def test_mcp_servers_have_required_fields(upstream_plugins_root: Path) -> None:
    servers = collect_all_mcp_servers(upstream_plugins_root)
    for s in servers:
        assert s.url.startswith("https://"), f"{s.slug}: bad url {s.url}"
        assert s.transport == "http"
        assert s.raw_manifest


def test_mcp_required_overlap_contains_known_real_aliases(
    upstream_plugins_root: Path,
) -> None:
    """capiq / daloopa / factset must resolve to real MCP slugs.

    - daloopa: direct slug match in .mcp.json
    - factset: direct slug match in .mcp.json
    - capiq:   alias of sp-global (S&P Global Kensho Capital IQ)
    """
    servers = collect_all_mcp_servers(upstream_plugins_root)
    slugs = {s.slug for s in servers}
    assert "daloopa" in slugs
    assert "factset" in slugs
    assert "sp-global" in slugs
    sp_global = next(s for s in servers if s.slug == "sp-global")
    assert sp_global.tool_name_map.get("capiq") == "sp-global"


def test_associations_dry_run(upstream_plugins_root: Path) -> None:
    agents = [
        parse_agent_file(md, pj) for md, pj in discover_agent_files(upstream_plugins_root)
    ]
    skills = [
        parse_skill_file(md, v) for md, v in discover_skill_files(upstream_plugins_root)
    ]
    mcps = collect_all_mcp_servers(upstream_plugins_root)

    vs = derive_vertical_skill_associations(skills)
    vm = derive_vertical_mcp_associations(mcps)
    am = derive_agent_mcp_candidates(agents, mcps)

    assert len(vs) >= 50
    vs_verticals = {v for v, _ in vs}
    assert vs_verticals.issubset(EXPECTED_VERTICALS)

    vm_verticals = {v for v, _ in vm}
    assert "financial-analysis" in vm_verticals
    assert {m for _, m in vm} == EXPECTED_MCP_SLUGS

    by_resolution: dict[str, set[str]] = {"matched": set(), "aliased": set(), "unmatched": set()}
    for c in am:
        by_resolution[c.resolution].add(c.referenced_alias)
    assert "daloopa" in by_resolution["matched"]
    assert "factset" in by_resolution["matched"]
    assert "capiq" in by_resolution["aliased"]
    assert {"internal-gl", "subledger", "screening"}.issubset(
        by_resolution["unmatched"]
    )


def test_parsers_do_not_modify_upstream(upstream_plugins_root: Path) -> None:
    vertical_pairs = discover_vertical_plugins(upstream_plugins_root)
    skill_pairs = discover_skill_files(upstream_plugins_root)[:5]
    mcp_files = discover_mcp_json_files(upstream_plugins_root)

    sample = (
        [p[0] for p in vertical_pairs[:3]]
        + [p[0] for p in skill_pairs]
        + list(mcp_files)
    )
    mtimes = {p: p.stat().st_mtime_ns for p in sample}
    modes = {p: stat.S_IMODE(p.stat().st_mode) for p in sample}

    for pj, slug in vertical_pairs:
        parse_vertical_plugin(pj, slug)
    for md, v in skill_pairs:
        parse_skill_file(md, v)
    for mj in mcp_files:
        parse_mcp_json(mj)

    for p, mtime in mtimes.items():
        assert p.stat().st_mtime_ns == mtime, f"parser modified {p}"
        assert stat.S_IMODE(p.stat().st_mode) == modes[p]


def test_missing_upstream_env_cli_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(UPSTREAM_ENV_VAR, raising=False)
    for cli in (import_verticals_main, import_skills_main, import_mcps_main, import_all_main):
        rc = cli([])
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
    for cli in (import_verticals_main, import_skills_main, import_mcps_main, import_all_main):
        rc = cli(["--apply"])
        assert rc == 2
        captured = capsys.readouterr()
        assert "SUPABASE_URL" in captured.err


def test_import_all_dry_run_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    upstream_plugins_root: Path,
) -> None:
    monkeypatch.setenv(UPSTREAM_ENV_VAR, str(upstream_plugins_root))
    rc = import_all_main([])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert '"supabase_write": false' in captured.out
    assert '"agents": 10' in captured.out
    assert '"verticals": 7' in captured.out
    assert '"mcps": 11' in captured.out


def test_skill_parser_rejects_missing_frontmatter(tmp_path: Path) -> None:
    md = tmp_path / "SKILL.md"
    md.write_text("no frontmatter\n", encoding="utf-8")
    with pytest.raises(SkillParseError):
        parse_skill_file(md, "x")


def test_vertical_parser_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VerticalParseError):
        parse_vertical_plugin(tmp_path / "missing.json", "x")
