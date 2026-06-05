from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from ..core.deps import require_admin_token
from ..core.supabase import get_supabase
from ..models.schemas import (
    McpServerCreateRequest,
    McpServerDetail,
    McpServerListItem,
    McpServerUpdateRequest,
)
from ..services import mcp_service

router = APIRouter(prefix="/api", tags=["mcp-servers"])


@router.get("/mcp-servers", response_model=list[McpServerListItem])
async def list_mcp_servers(
    client: AsyncClient = Depends(get_supabase),
) -> list[McpServerListItem]:
    return await mcp_service.list_mcp_servers(client)


@router.get("/mcp-servers/{server_id}", response_model=McpServerDetail)
async def get_mcp_server(
    server_id: UUID,
    client: AsyncClient = Depends(get_supabase),
) -> McpServerDetail:
    result = await mcp_service.get_mcp_server(client, str(server_id))
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "MCP server not found",
                "status": 404,
                "code": "mcp_server_not_found",
                "detail": f"No MCP server with id '{server_id}'.",
            },
        )
    return result


@router.post(
    "/mcp-servers",
    response_model=McpServerDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_token)],
)
async def create_mcp_server(
    req: McpServerCreateRequest,
    client: AsyncClient = Depends(get_supabase),
) -> McpServerDetail:
    return await mcp_service.create_mcp_server(client, req)


@router.put(
    "/mcp-servers/{server_id}",
    response_model=McpServerDetail,
    dependencies=[Depends(require_admin_token)],
)
async def update_mcp_server(
    server_id: UUID,
    req: McpServerUpdateRequest,
    client: AsyncClient = Depends(get_supabase),
) -> McpServerDetail:
    result = await mcp_service.update_mcp_server(client, str(server_id), req)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "MCP server not found",
                "status": 404,
                "code": "mcp_server_not_found",
                "detail": f"No MCP server with id '{server_id}'.",
            },
        )
    return result
