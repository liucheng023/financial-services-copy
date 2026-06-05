from __future__ import annotations

from typing import TYPE_CHECKING

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
    has_key, masked = _mask_api_key(created.get("api_key"))
    return McpServerDetail(
        id=created["id"],
        slug=created["slug"],
        name=created["name"],
        url=created["url"],
        transport=created["transport"],
        description=created.get("description"),
        has_api_key=has_key,
        tool_name_map=created.get("tool_name_map", {}),
        masked_api_key=masked,
    )


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
