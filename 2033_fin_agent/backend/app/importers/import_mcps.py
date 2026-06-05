"""CLI for the MCP server importer."""

from __future__ import annotations

import argparse
import json
import sys

from ._cli_common import (
    MissingUpstreamPathError,
    resolve_upstream_root,
    supabase_env_available,
)
from .mcp_parser import collect_all_mcp_servers, discover_mcp_json_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import upstream MCP servers.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write parsed MCPs to Supabase. Requires SUPABASE_URL and "
        "SUPABASE_SERVICE_KEY. Writer failure exits 3.",
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

    json_files = discover_mcp_json_files(upstream_root)
    servers = collect_all_mcp_servers(upstream_root)

    written_mcps = 0
    written_vm = 0
    if args.apply:
        from .associations import derive_vertical_mcp_associations
        from .supabase_writer import (
            build_client,
            upsert_mcp_servers,
            upsert_vertical_mcps,
        )

        try:
            client = build_client()
            written_mcps = upsert_mcp_servers(client, servers)
            vm_pairs = derive_vertical_mcp_associations(servers)
            written_vm = upsert_vertical_mcps(client, vm_pairs)
        except Exception as exc:
            print(f"WRITE_ERROR mcps: {exc}", file=sys.stderr)
            return 3

    summary = {
        "upstream_root": str(upstream_root),
        "mcp_json_files": [str(p) for p in json_files],
        "discovered_servers": len(servers),
        "supabase_write": bool(args.apply),
        "written_mcps": written_mcps,
        "written_vertical_mcps": written_vm,
        "servers": [
            {
                "slug": s.slug,
                "name": s.name,
                "url": s.url,
                "transport": s.transport,
                "tool_name_map": s.tool_name_map,
                "source": s.source_path,
            }
            for s in servers
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
