"""CLI entry point for the agent importer.

Phase 1 modes:

* ``--dry-run`` (default): parse only. Print a JSON summary of each parsed
  agent. Never touches Supabase. Always available, no Supabase env required.
* ``--apply``: write parsed agents to Supabase. Requires ``SUPABASE_URL`` and
  ``SUPABASE_SERVICE_KEY`` env vars. Raises if either is missing. NOT
  implemented in Task 2 — Task 2 ships parse-only. The flag is reserved so
  future tasks add the writer without changing the CLI surface.

The importer is read-only relative to ``$UPSTREAM_PLUGINS_PATH``. It never
opens any upstream file for writing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

from ._cli_common import (
    UPSTREAM_ENV_VAR,
    MissingUpstreamPathError,
)
from ._cli_common import (
    resolve_upstream_root as _resolve_upstream_root,
)
from .agent_parser import AgentParseError, discover_agent_files, parse_agent_file

__all__ = [
    "UPSTREAM_ENV_VAR",
    "MissingUpstreamPathError",
    "_resolve_upstream_root",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import upstream agents.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Parse only; never write to Supabase. Default.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write parsed agents to Supabase. Requires SUPABASE_URL and "
        "SUPABASE_SERVICE_KEY. NOT implemented in Task 2.",
    )
    args = parser.parse_args(argv)

    try:
        upstream_root = _resolve_upstream_root()
    except MissingUpstreamPathError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.apply and (
        not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY")
    ):
        print(
            "error: --apply requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.",
            file=sys.stderr,
        )
        return 2

    pairs = discover_agent_files(upstream_root)
    parsed_objs = []
    parsed = []
    errors = 0
    for md_path, plugin_json in pairs:
        try:
            agent = parse_agent_file(md_path, plugin_json)
        except AgentParseError as exc:
            print(f"PARSE_ERROR {md_path}: {exc}", file=sys.stderr)
            errors += 1
            continue
        parsed_objs.append(agent)
        parsed.append(asdict(agent))

    written = 0
    if args.apply and errors == 0:
        from .supabase_writer import build_client, upsert_agents

        try:
            client = build_client()
            written = upsert_agents(client, parsed_objs)
        except Exception as exc:
            print(f"WRITE_ERROR agents: {exc}", file=sys.stderr)
            return 3

    summary = {
        "upstream_root": str(upstream_root),
        "discovered": len(pairs),
        "parsed": len(parsed),
        "errors": errors,
        "supabase_write": bool(args.apply),
        "written": written,
        "agents": [
            {
                "slug": a["slug"],
                "name": a["name"],
                "system_prompt_chars": len(a["system_prompt"]),
                "has_workflow": bool(a["workflow"]),
                "has_guardrails": bool(a["guardrails"]),
                "has_outputs": bool(a["outputs"]),
            }
            for a in parsed
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
