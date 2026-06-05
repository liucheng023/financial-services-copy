"""CLI for the skill importer."""

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
from .skill_parser import SkillParseError, discover_skill_files, parse_skill_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import upstream skills.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write parsed skills to Supabase. Requires SUPABASE_URL and "
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

    pairs = discover_skill_files(upstream_root)
    parsed_objs = []
    parsed = []
    errors = 0
    for md_path, v_slug in pairs:
        try:
            s = parse_skill_file(md_path, v_slug)
        except SkillParseError as exc:
            print(f"PARSE_ERROR {md_path}: {exc}", file=sys.stderr)
            errors += 1
            continue
        parsed_objs.append(s)
        parsed.append(asdict(s))

    by_vertical: dict[str, int] = {}
    for s in parsed:
        v = s["vertical_slug"] or "(none)"
        by_vertical[v] = by_vertical.get(v, 0) + 1

    written_skills = 0
    written_vs = 0
    if args.apply and errors == 0:
        from .associations import derive_vertical_skill_associations
        from .supabase_writer import (
            build_client,
            upsert_skills,
            upsert_vertical_skills,
        )

        try:
            client = build_client()
            written_skills = upsert_skills(client, parsed_objs)
            vs_pairs = derive_vertical_skill_associations(parsed_objs)
            written_vs = upsert_vertical_skills(client, vs_pairs)
        except Exception as exc:
            print(f"WRITE_ERROR skills: {exc}", file=sys.stderr)
            return 3

    summary = {
        "upstream_root": str(upstream_root),
        "discovered": len(pairs),
        "parsed": len(parsed),
        "errors": errors,
        "supabase_write": bool(args.apply),
        "written_skills": written_skills,
        "written_vertical_skills": written_vs,
        "by_vertical": dict(sorted(by_vertical.items())),
        "sample_skills": [
            {
                "slug": s["slug"],
                "vertical": s["vertical_slug"],
                "content_chars": len(s["content"]),
                "has_description": bool(s["description"]),
            }
            for s in parsed[:5]
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
