from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from supabase import AsyncClient

from ..core.supabase import get_supabase
from ..models.schemas import (
    SendMessageRequest,
    SessionCreateRequest,
    SessionDetail,
    SessionListItem,
)
from ..services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])


def _not_found(code: str, title: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "type": "about:blank",
            "title": title,
            "status": 404,
            "code": code,
            "detail": detail,
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


@router.post(
    "/sessions",
    response_model=SessionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    req: SessionCreateRequest,
    client: AsyncClient = Depends(get_supabase),
) -> SessionDetail:
    try:
        return await chat_service.create_session(client, req)
    except chat_service.AgentNotFoundError as exc:
        raise _not_found(
            "agent_not_found",
            "Agent not found",
            f"No agent with slug '{req.agent_slug}'.",
        ) from exc


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    client: AsyncClient = Depends(get_supabase),
) -> list[SessionListItem]:
    return await chat_service.list_sessions(client)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: UUID,
    client: AsyncClient = Depends(get_supabase),
) -> SessionDetail:
    result = await chat_service.get_session(client, str(session_id))
    if result is None:
        raise _not_found(
            "session_not_found",
            "Session not found",
            f"No chat session with id '{session_id}'.",
        )
    return result





@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: UUID,
    req: SendMessageRequest,
    client: AsyncClient = Depends(get_supabase),
) -> StreamingResponse:
    try:
        event_stream = await chat_service.prepare_stream(
            client, str(session_id), req.content
        )
    except chat_service.SessionNotFoundError as exc:
        raise _not_found(
            "session_not_found",
            "Session not found",
            f"No chat session with id '{session_id}'.",
        ) from exc
    except chat_service.NoDefaultModelError as exc:
        raise _no_default() from exc

    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
