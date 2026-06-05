from __future__ import annotations

from typing import TYPE_CHECKING

from ..adapters.mcp_adapter import MCPServerConfig, MCPToolset, create_openai_toolset
from ..models.schemas import (
    McpServerCreateRequest,
    McpServerDetail,
    McpServerListItem,
    McpServerUpdateRequest,
)

if TYPE_CHECKING:
    from supabase import AsyncClient

from .agent_service import _mask_api_key


async def list_mcp_servers(client: AsyncClient) -> list[McpServerListItem]:
    resp = await (
        client.table("mcp_servers")
        .select("id,slug,name,url,transport,description,api_key")
        .order("name")
        .execute()
    )
    items: list[McpServerListItem] = []
    for r in resp.data or []:
        has_key, _ = _mask_api_key(r.get("api_key"))
        items.append(
            McpServerListItem(
                id=r["id"],
                slug=r["slug"],
                name=r["name"],
                url=r["url"],
                transport=r["transport"],
                description=r.get("description"),
                has_api_key=has_key,
            )
        )
    return items


async def get_mcp_server(client: AsyncClient, server_id: str) -> McpServerDetail | None:
    resp = await (
        client.table("mcp_servers")
        .select("*")
        .eq("id", server_id)
        .maybe_single()
        .execute()
    )
    row = resp.data
    if not row:
        return None
    return _detail_from_row(row)


async def create_mcp_server(
    client: AsyncClient, req: McpServerCreateRequest
) -> McpServerDetail:
    row_data: dict = {
        "slug": req.slug,
        "name": req.name,
        "url": req.url,
        "transport": req.transport,
        "tool_name_map": req.tool_name_map,
    }
    if req.description is not None:
        row_data["description"] = req.description
    if req.api_key is not None:
        row_data["api_key"] = req.api_key

    resp = await client.table("mcp_servers").insert(row_data).execute()
    created = resp.data[0] if resp.data else {}
    return _detail_from_row(created)


async def update_mcp_server(
    client: AsyncClient, server_id: str, req: McpServerUpdateRequest
) -> McpServerDetail | None:
    existing = await get_mcp_server(client, server_id)
    if existing is None:
        return None

    updates: dict = {}
    for field in ("name", "url", "transport", "description", "tool_name_map"):
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val
    if req.api_key is not None:
        updates["api_key"] = req.api_key

    if not updates:
        return existing

    resp = (
        await client.table("mcp_servers")
        .update(updates)
        .eq("id", server_id)
        .execute()
    )
    row = resp.data[0] if resp.data else {}
    return _detail_from_row(row)


async def list_agent_mcp_configs(client: AsyncClient, agent_slug: str) -> list[MCPServerConfig]:
    agent_resp = await (
        client.table("agents")
        .select("id")
        .eq("slug", agent_slug)
        .maybe_single()
        .execute()
    )
    agent = agent_resp.data
    if not agent:
        return []

    link_resp = await (
        client.table("agent_mcps")
        .select("mcp_server_id")
        .eq("agent_id", agent["id"])
        .execute()
    )
    mcp_ids = [r["mcp_server_id"] for r in link_resp.data or []]
    if not mcp_ids:
        return []

    server_resp = await (
        client.table("mcp_servers")
        .select("id,slug,name,url,transport,api_key,tool_name_map")
        .in_("id", mcp_ids)
        .execute()
    )
    return [_config_from_row(row) for row in server_resp.data or []]


async def create_agent_mcp_toolset(client: AsyncClient, agent_slug: str) -> MCPToolset:
    configs = await list_agent_mcp_configs(client, agent_slug)
    return await create_openai_toolset(configs)


def _detail_from_row(row: dict) -> McpServerDetail:
    has_key, masked = _mask_api_key(row.get("api_key"))
    return McpServerDetail(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        url=row["url"],
        transport=row["transport"],
        description=row.get("description"),
        has_api_key=has_key,
        tool_name_map=row.get("tool_name_map", {}),
        masked_api_key=masked,
    )


def _config_from_row(row: dict) -> MCPServerConfig:
    return MCPServerConfig(
        slug=row["slug"],
        name=row["name"],
        url=row["url"],
        transport=row.get("transport") or "http",
        api_key=row.get("api_key"),
        tool_name_map=row.get("tool_name_map", {}),
    )
