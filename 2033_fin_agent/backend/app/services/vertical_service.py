from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.schemas import (
    McpServerSummary,
    SkillSummary,
    VerticalDetail,
    VerticalListItem,
)

if TYPE_CHECKING:
    from supabase import AsyncClient

from .agent_service import _mask_api_key


async def list_verticals(client: AsyncClient) -> list[VerticalListItem]:
    resp = await (
        client.table("verticals")
        .select("slug,name,description,id")
        .order("name")
        .execute()
    )
    rows = resp.data or []
    v_ids = [r["id"] for r in rows]
    skill_counts: dict[str, int] = {}
    mcp_counts: dict[str, int] = {}
    if v_ids:
        sk = await (
            client.table("vertical_skills")
            .select("vertical_id")
            .in_("vertical_id", v_ids)
            .execute()
        )
        for r in sk.data or []:
            skill_counts[r["vertical_id"]] = skill_counts.get(r["vertical_id"], 0) + 1
        mc = await (
            client.table("vertical_mcps")
            .select("vertical_id")
            .in_("vertical_id", v_ids)
            .execute()
        )
        for r in mc.data or []:
            mcp_counts[r["vertical_id"]] = mcp_counts.get(r["vertical_id"], 0) + 1
    return [
        VerticalListItem(
            slug=r["slug"],
            name=r["name"],
            description=r.get("description"),
            skill_count=skill_counts.get(r["id"], 0),
            mcp_count=mcp_counts.get(r["id"], 0),
        )
        for r in rows
    ]


async def get_vertical_by_slug(client: AsyncClient, slug: str) -> VerticalDetail | None:
    resp = await (
        client.table("verticals")
        .select("*")
        .eq("slug", slug)
        .maybe_single()
        .execute()
    )
    row = resp.data
    if not row:
        return None

    skill_link_rows = await (
        client.table("vertical_skills")
        .select("skill_id")
        .eq("vertical_id", row["id"])
        .execute()
    )
    skill_ids = [r["skill_id"] for r in skill_link_rows.data or []]
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
        client.table("vertical_mcps")
        .select("mcp_server_id")
        .eq("vertical_id", row["id"])
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

    return VerticalDetail(
        slug=row["slug"],
        name=row["name"],
        description=row.get("description"),
        skills=skills,
        mcps=mcps,
    )
