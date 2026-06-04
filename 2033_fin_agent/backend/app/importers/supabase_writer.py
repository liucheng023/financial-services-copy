"""Supabase writers for Task 3b.

Encapsulates every Supabase upsert the importers need. Each writer:

* takes a list of parsed records,
* upserts them on their natural conflict key (``slug`` for entity tables,
  composite FK tuples for association tables),
* is idempotent — a re-run upserts the same rows with no duplicates,
* never invents an ``api_key`` value: a row that has no key writes NULL,
* returns a count of upserted rows for the operator report.

Synchronous on purpose. The importer CLIs are one-shot scripts run outside
the FastAPI event loop; using the sync ``supabase`` client keeps them
simple and removes the need for an async runner inside ``__main__``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from .agent_parser import ParsedAgent
from .associations import AgentMcpCandidate
from .mcp_parser import ParsedMcpServer
from .skill_parser import ParsedSkill
from .vertical_parser import ParsedVertical


class SupabaseEnvMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class WriteReport:
    agents: int = 0
    verticals: int = 0
    skills: int = 0
    mcp_servers: int = 0
    vertical_skills: int = 0
    vertical_mcps: int = 0
    agent_mcps: int = 0
    agent_mcps_skipped_unmatched: int = 0


def _require_env() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SupabaseEnvMissingError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY are required for --apply."
        )
    return url, key


def build_client():
    """Build a sync Supabase client. Imported lazily to keep dry-run import-free."""
    url, key = _require_env()
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "supabase-py>=2 is required for --apply. Install via `uv sync` "
            "(see backend/pyproject.toml)."
        ) from exc
    return create_client(url, key)


def upsert_verticals(client, verticals: Iterable[ParsedVertical]) -> int:
    rows = [
        {
            "slug": v.slug,
            "name": v.name,
            "description": v.description,
            "raw_manifest": v.raw_manifest,
        }
        for v in verticals
    ]
    if not rows:
        return 0
    client.table("verticals").upsert(rows, on_conflict="slug").execute()
    return len(rows)


def upsert_agents(client, agents: Iterable[ParsedAgent]) -> int:
    rows = [
        {
            "slug": a.slug,
            "name": a.name,
            "description": a.description,
            "system_prompt": a.system_prompt,
            "workflow": a.workflow,
            "guardrails": a.guardrails,
            "outputs": a.outputs,
            "raw_frontmatter": a.raw_frontmatter,
        }
        for a in agents
    ]
    if not rows:
        return 0
    client.table("agents").upsert(rows, on_conflict="slug").execute()
    return len(rows)


def upsert_mcp_servers(client, mcps: Iterable[ParsedMcpServer]) -> int:
    rows = [
        {
            "slug": m.slug,
            "name": m.name,
            "url": m.url,
            "transport": m.transport,
            "description": m.description,
            "tool_name_map": m.tool_name_map,
            "raw_manifest": m.raw_manifest,
            # api_key intentionally absent → NULL. Operators fill it via the
            # admin UI; the importer never invents a placeholder value.
        }
        for m in mcps
    ]
    if not rows:
        return 0
    client.table("mcp_servers").upsert(rows, on_conflict="slug").execute()
    return len(rows)


def _fetch_slug_to_id(client, table: str) -> dict[str, str]:
    rows = client.table(table).select("id,slug").execute().data or []
    return {r["slug"]: r["id"] for r in rows if r.get("slug") and r.get("id")}


def upsert_skills(
    client,
    skills: Iterable[ParsedSkill],
) -> int:
    vertical_id_by_slug = _fetch_slug_to_id(client, "verticals")
    rows: list[dict] = []
    for s in skills:
        vertical_id = vertical_id_by_slug.get(s.vertical_slug) if s.vertical_slug else None
        rows.append(
            {
                "slug": s.slug,
                "name": s.name,
                "description": s.description,
                "vertical_id": vertical_id,
                "content": s.content,
                "raw_frontmatter": s.raw_frontmatter,
            }
        )
    if not rows:
        return 0
    client.table("skills").upsert(rows, on_conflict="slug").execute()
    return len(rows)


def upsert_vertical_skills(
    client,
    pairs: Iterable[tuple[str, str]],
) -> int:
    vertical_id_by_slug = _fetch_slug_to_id(client, "verticals")
    skill_id_by_slug = _fetch_slug_to_id(client, "skills")
    rows = []
    for v_slug, s_slug in pairs:
        v_id = vertical_id_by_slug.get(v_slug)
        s_id = skill_id_by_slug.get(s_slug)
        if v_id and s_id:
            rows.append({"vertical_id": v_id, "skill_id": s_id})
    if not rows:
        return 0
    client.table("vertical_skills").upsert(
        rows, on_conflict="vertical_id,skill_id"
    ).execute()
    return len(rows)


def upsert_vertical_mcps(
    client,
    pairs: Iterable[tuple[str, str]],
) -> int:
    vertical_id_by_slug = _fetch_slug_to_id(client, "verticals")
    mcp_id_by_slug = _fetch_slug_to_id(client, "mcp_servers")
    rows = []
    for v_slug, m_slug in pairs:
        v_id = vertical_id_by_slug.get(v_slug)
        m_id = mcp_id_by_slug.get(m_slug)
        if v_id and m_id:
            rows.append({"vertical_id": v_id, "mcp_server_id": m_id})
    if not rows:
        return 0
    client.table("vertical_mcps").upsert(
        rows, on_conflict="vertical_id,mcp_server_id"
    ).execute()
    return len(rows)


def upsert_agent_mcps(
    client,
    candidates: Iterable[AgentMcpCandidate],
) -> tuple[int, int]:
    """Write matched + aliased candidates. Return (written, unmatched_skipped)."""
    agent_id_by_slug = _fetch_slug_to_id(client, "agents")
    mcp_id_by_slug = _fetch_slug_to_id(client, "mcp_servers")
    rows = []
    skipped = 0
    seen: set[tuple[str, str]] = set()
    for c in candidates:
        if c.resolution == "unmatched" or not c.resolved_mcp_slug:
            skipped += 1
            continue
        a_id = agent_id_by_slug.get(c.agent_slug)
        m_id = mcp_id_by_slug.get(c.resolved_mcp_slug)
        if not a_id or not m_id:
            skipped += 1
            continue
        key = (a_id, m_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"agent_id": a_id, "mcp_server_id": m_id})
    if not rows:
        return 0, skipped
    client.table("agent_mcps").upsert(
        rows, on_conflict="agent_id,mcp_server_id"
    ).execute()
    return len(rows), skipped
