from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from ..core.supabase import get_supabase
from ..models.schemas import VerticalDetail, VerticalListItem
from ..services import vertical_service

router = APIRouter(prefix="/api", tags=["verticals"])


@router.get("/verticals", response_model=list[VerticalListItem])
async def list_verticals(
    client: AsyncClient = Depends(get_supabase),
) -> list[VerticalListItem]:
    return await vertical_service.list_verticals(client)


@router.get("/verticals/{slug}", response_model=VerticalDetail)
async def get_vertical(
    slug: str,
    client: AsyncClient = Depends(get_supabase),
) -> VerticalDetail:
    result = await vertical_service.get_vertical_by_slug(client, slug)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Vertical not found",
                "status": 404,
                "code": "vertical_not_found",
                "detail": f"No vertical with slug '{slug}'.",
            },
        )
    return result
