from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.schemas import AgentDetail, AgentListItem, McpServerSummary, SkillSummary

if TYPE_CHECKING:
    from supabase import AsyncClient


def _mask_api_key(raw: str | None) -> tuple[bool, str | None]:
    if not raw:
        return False, None
    return True, f"****{raw[-4:]}"


async def list_agents(client: AsyncClient) -> list[AgentListItem]:
    resp = await (
        client.table("agents")
        .select("slug,name,description,id")
        .order("name")
        .execute()
    )
    rows = resp.data or []
    agent_ids = [r["id"] for r in rows]
    skill_counts: dict[str, int] = {}
    mcp_counts: dict[str, int] = {}
    if agent_ids:
        sk = await (
            client.table("agent_skills")
            .select("agent_id")
            .in_("agent_id", agent_ids)
            .execute()
        )
        for r in sk.data or []:
            skill_counts[r["agent_id"]] = skill_counts.get(r["agent_id"], 0) + 1
        mc = await (
            client.table("agent_mcps")
            .select("agent_id")
            .in_("agent_id", agent_ids)
            .execute()
        )
        for r in mc.data or []:
            mcp_counts[r["agent_id"]] = mcp_counts.get(r["agent_id"], 0) + 1
    return [
        AgentListItem(
            slug=r["slug"],
            name=r["name"],
            description=r.get("description"),
            skill_count=skill_counts.get(r["id"], 0),
            mcp_count=mcp_counts.get(r["id"], 0),
        )
        for r in rows
    ]


async def get_agent_by_slug(client: AsyncClient, slug: str) -> AgentDetail | None:
    resp = await (
        client.table("agents")
        .select("*")
        .eq("slug", slug)
        .maybe_single()
        .execute()
    )
    row = resp.data
    if not row:
        return None

    skill_rows = await (
        client.table("agent_skills")
        .select("skill_id")
        .eq("agent_id", row["id"])
        .execute()
    )
    skill_ids = [r["skill_id"] for r in skill_rows.data or []]
    skills: list[SkillSummary] = []
    if skill_ids:
        sk_resp = await (
            client.table("skills")
            .select("slug,name,description")
            .in_("id", skill_ids)
            .execute()
        )
        skills = [SkillSummary(**s) for s in sk_resp.data or []]

    mcp_link_rows = await (
        client.table("agent_mcps")
        .select("mcp_server_id")
        .eq("agent_id", row["id"])
        .execute()
    )
    mcp_ids = [r["mcp_server_id"] for r in mcp_link_rows.data or []]
    mcps: list[McpServerSummary] = []
    if mcp_ids:
        mc_resp = await (
            client.table("mcp_servers")
            .select("id,slug,name,url,transport,api_key")
            .in_("id", mcp_ids)
            .execute()
        )
        for m in mc_resp.data or []:
            has_key, _ = _mask_api_key(m.get("api_key"))
            mcps.append(
                McpServerSummary(
                    id=m["id"],
                    slug=m["slug"],
                    name=m["name"],
                    url=m["url"],
                    transport=m["transport"],
                    has_api_key=has_key,
                )
            )

    return AgentDetail(
        slug=row["slug"],
        name=row["name"],
        description=row.get("description"),
        system_prompt=row["system_prompt"],
        workflow=row.get("workflow"),
        guardrails=row.get("guardrails"),
        outputs=row.get("outputs"),
        skills=skills,
        mcps=mcps,
    )
