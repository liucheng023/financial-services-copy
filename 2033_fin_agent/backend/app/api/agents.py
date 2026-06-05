from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from ..core.supabase import get_supabase
from ..models.schemas import AgentDetail, AgentListItem
from ..services import agent_service

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents", response_model=list[AgentListItem])
async def list_agents(client: AsyncClient = Depends(get_supabase)) -> list[AgentListItem]:
    return await agent_service.list_agents(client)


@router.get("/agents/{slug}", response_model=AgentDetail)
async def get_agent(slug: str, client: AsyncClient = Depends(get_supabase)) -> AgentDetail:
    result = await agent_service.get_agent_by_slug(client, slug)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Agent not found",
                "status": 404,
                "code": "agent_not_found",
                "detail": f"No agent with slug '{slug}'.",
            },
        )
    return result
