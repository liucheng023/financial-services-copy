from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient

from ..core.deps import require_admin_token
from ..core.supabase import get_supabase
from ..models.schemas import (
    ModelConfigCreateRequest,
    ModelConfigDetail,
    ModelConfigListItem,
    ModelConfigTestResult,
    ModelConfigUpdateRequest,
)
from ..services import model_config_service

router = APIRouter(prefix="/api", tags=["model-configs"])


def _not_found(config_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "type": "about:blank",
            "title": "Model config not found",
            "status": 404,
            "code": "model_config_not_found",
            "detail": f"No model config with id '{config_id}'.",
        },
    )


def _no_default() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "type": "about:blank",
            "title": "No default model config",
            "status": 404,
            "code": "model_config_not_found",
            "detail": "No model config is currently marked as default.",
        },
    )


@router.get("/model-configs", response_model=list[ModelConfigListItem])
async def list_model_configs(
    client: AsyncClient = Depends(get_supabase),
) -> list[ModelConfigListItem]:
    return await model_config_service.list_model_configs(client)


@router.get("/model-configs/default", response_model=ModelConfigDetail)
async def get_default_model_config(
    client: AsyncClient = Depends(get_supabase),
) -> ModelConfigDetail:
    result = await model_config_service.get_default_model_config(client)
    if result is None:
        raise _no_default()
    return result


@router.post(
    "/model-configs",
    response_model=ModelConfigDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_token)],
)
async def create_model_config(
    req: ModelConfigCreateRequest,
    client: AsyncClient = Depends(get_supabase),
) -> ModelConfigDetail:
    return await model_config_service.create_model_config(client, req)


@router.put(
    "/model-configs/{config_id}",
    response_model=ModelConfigDetail,
    dependencies=[Depends(require_admin_token)],
)
async def update_model_config(
    config_id: UUID,
    req: ModelConfigUpdateRequest,
    client: AsyncClient = Depends(get_supabase),
) -> ModelConfigDetail:
    result = await model_config_service.update_model_config(
        client, str(config_id), req
    )
    if result is None:
        raise _not_found(str(config_id))
    return result


@router.post(
    "/model-configs/{config_id}/test",
    response_model=ModelConfigTestResult,
    dependencies=[Depends(require_admin_token)],
)
async def test_model_config(
    config_id: UUID,
    client: AsyncClient = Depends(get_supabase),
) -> ModelConfigTestResult:
    result = await model_config_service.test_model_connection(
        client, str(config_id)
    )
    if result is None:
        raise _not_found(str(config_id))
    return result
