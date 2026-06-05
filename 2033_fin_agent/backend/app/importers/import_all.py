"""CLI that runs all importers, prints a consolidated summary.

Includes association reports:
- vertical_skills:  derived from skill path -> vertical
- vertical_mcps:    derived from .mcp.json path -> vertical
- agent_mcps:       cross-referenced from agent ``tools:`` frontmatter against
  MCP slugs and known aliases. Reports matched / aliased / unmatched buckets
  so operators see which tool refs are placeholders.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from ._cli_common import (
    MissingUpstreamPathError,
    resolve_upstream_root,
    supabase_env_available,
)
from .agent_parser import AgentParseError, discover_agent_files, parse_agent_file
from .associations import (
    derive_agent_mcp_candidates,
    derive_vertical_mcp_associations,
    derive_vertical_skill_associations,
)
from .mcp_parser import collect_all_mcp_servers
from .skill_parser import SkillParseError, discover_skill_files, parse_skill_file
from .vertical_parser import VerticalParseError, discover_vertical_plugins, parse_vertical_plugin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run all parse-only importers and emit a consolidated report."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write to Supabase. Requires SUPABASE_URL and SUPABASE_SERVICE_KEY. "
        "Writer failure exits 3.",
    )
    args = parser.parse_args(argv)

    try:
        upstream_root = resolve_upstream_root()
    except MissingUpstreamPathError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.apply and not supabase_env_available():
        print(
            "error: --apply requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.",
            file=sys.stderr,
        )
        return 2

    errors = 0

    agents = []
    for md_path, plugin_json in discover_agent_files(upstream_root):
        try:
            agents.append(parse_agent_file(md_path, plugin_json))
        except AgentParseError as exc:
            print(f"PARSE_ERROR agent {md_path}: {exc}", file=sys.stderr)
            errors += 1

    verticals = []
    for plugin_json, slug in discover_vertical_plugins(upstream_root):
        try:
            verticals.append(parse_vertical_plugin(plugin_json, slug))
        except VerticalParseError as exc:
            print(f"PARSE_ERROR vertical {plugin_json}: {exc}", file=sys.stderr)
            errors += 1

    skills = []
    for md_path, v_slug in discover_skill_files(upstream_root):
        try:
            skills.append(parse_skill_file(md_path, v_slug))
        except SkillParseError as exc:
            print(f"PARSE_ERROR skill {md_path}: {exc}", file=sys.stderr)
            errors += 1

    mcps = collect_all_mcp_servers(upstream_root)

    vs_assoc = derive_vertical_skill_associations(skills)
    vm_assoc = derive_vertical_mcp_associations(mcps)
    am_candidates = derive_agent_mcp_candidates(agents, mcps)

    resolution_counts: dict[str, int] = {"matched": 0, "aliased": 0, "unmatched": 0}
    for c in am_candidates:
        resolution_counts[c.resolution] = resolution_counts.get(c.resolution, 0) + 1

    written: dict[str, int] = {
        "agents": 0,
        "verticals": 0,
        "skills": 0,
        "mcp_servers": 0,
        "vertical_skills": 0,
        "vertical_mcps": 0,
        "agent_mcps": 0,
        "agent_mcps_skipped_unmatched": 0,
    }
    if args.apply and errors == 0:
        from .supabase_writer import (
            build_client,
            upsert_agent_mcps,
            upsert_agents,
            upsert_mcp_servers,
            upsert_skills,
            upsert_vertical_mcps,
            upsert_vertical_skills,
            upsert_verticals,
        )

        try:
            client = build_client()
            written["verticals"] = upsert_verticals(client, verticals)
            written["mcp_servers"] = upsert_mcp_servers(client, mcps)
            written["agents"] = upsert_agents(client, agents)
            written["skills"] = upsert_skills(client, skills)
            written["vertical_skills"] = upsert_vertical_skills(client, vs_assoc)
            written["vertical_mcps"] = upsert_vertical_mcps(client, vm_assoc)
            am_written, am_skipped = upsert_agent_mcps(client, am_candidates)
            written["agent_mcps"] = am_written
            written["agent_mcps_skipped_unmatched"] = am_skipped
        except Exception as exc:
            print(f"WRITE_ERROR import_all: {exc}", file=sys.stderr)
            return 3

    report = {
        "upstream_root": str(upstream_root),
        "supabase_write": bool(args.apply),
        "errors": errors,
        "counts": {
            "agents": len(agents),
            "verticals": len(verticals),
            "skills": len(skills),
            "mcps": len(mcps),
            "vertical_skills": len(vs_assoc),
            "vertical_mcps": len(vm_assoc),
            "agent_mcp_candidates": len(am_candidates),
        },
        "written": written,
        "agent_mcp_resolution": resolution_counts,
        "verticals": [v.slug for v in verticals],
        "mcps": [m.slug for m in mcps],
        "agent_mcp_candidates": [asdict(c) for c in am_candidates],
    }
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
