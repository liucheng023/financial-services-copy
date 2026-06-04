"""Supabase connectivity smoke check.

Runs ``SELECT 1``-equivalent reads against the tables the Phase 1
migration is expected to expose, so an operator can confirm the
backend can talk to Supabase before flipping any importer's
``--apply`` switch. Read-only — never inserts, updates, or deletes.

Exit codes:
    0   all probed tables responded
    2   required env (``SUPABASE_URL`` and/or ``SUPABASE_SERVICE_KEY``) missing
    3   Supabase responded with an error for at least one table
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Sequence

EXPECTED_TABLES = (
    "agents",
    "verticals",
    "skills",
    "mcp_servers",
    "agent_skills",
    "agent_mcps",
    "vertical_skills",
    "vertical_mcps",
    "chat_sessions",
    "chat_messages",
    "model_configs",
)


def _missing_env() -> list[str]:
    return [v for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY") if not os.environ.get(v)]


async def _probe(client, table: str) -> dict[str, object]:
    try:
        await client.table(table).select("*", count="exact", head=True).limit(0).execute()
        return {"table": table, "ok": True}
    except Exception as exc:  # noqa: BLE001 — we re-raise via exit code
        return {"table": table, "ok": False, "error": type(exc).__name__, "message": str(exc)}


async def _run() -> int:
    from app.core.supabase import get_supabase

    client = await get_supabase()
    results = [await _probe(client, t) for t in EXPECTED_TABLES]
    report = {
        "supabase_write": False,
        "expected_tables": list(EXPECTED_TABLES),
        "results": results,
        "errors": [r for r in results if not r["ok"]],
    }
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 3


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    missing = _missing_env()
    if missing:
        print(
            "ERROR: missing required env: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2
    return asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
