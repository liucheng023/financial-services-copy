"""CLI for the vertical-plugin importer (Task 3a: parse-only)."""

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
from .vertical_parser import VerticalParseError, discover_vertical_plugins, parse_vertical_plugin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import upstream verticals.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write parsed verticals to Supabase. Requires SUPABASE_URL and "
        "SUPABASE_SERVICE_KEY. NOT implemented in Task 3a.",
    )
    args = parser.parse_args(argv)

    try:
        upstream_root = resolve_upstream_root()
    except MissingUpstreamPathError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.apply:
        if not supabase_env_available():
            print(
                "error: --apply requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.",
                file=sys.stderr,
            )
            return 2
        print(
            "error: --apply is not implemented in Task 3a (parse-only gate). "
            "Use --dry-run.",
            file=sys.stderr,
        )
        return 2

    pairs = discover_vertical_plugins(upstream_root)
    parsed = []
    errors = 0
    for plugin_json, slug in pairs:
        try:
            v = parse_vertical_plugin(plugin_json, slug)
        except VerticalParseError as exc:
            print(f"PARSE_ERROR {plugin_json}: {exc}", file=sys.stderr)
            errors += 1
            continue
        parsed.append(asdict(v))

    summary = {
        "upstream_root": str(upstream_root),
        "discovered": len(pairs),
        "parsed": len(parsed),
        "errors": errors,
        "verticals": [
            {
                "slug": v["slug"],
                "name": v["name"],
                "has_description": bool(v["description"]),
            }
            for v in parsed
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
