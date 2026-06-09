from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from ..adapters.llm_adapter import (
    ChatStreamer,
    LLMStreamConfig,
    StreamEvent,
    http_stream_chat_completion,
)
from ..models.schemas import (
    ChatMessage,
    SessionCreateRequest,
    SessionDetail,
    SessionListItem,
)

if TYPE_CHECKING:
    from supabase import AsyncClient


class ChatServiceError(Exception):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SessionNotFoundError(ChatServiceError):
    def __init__(self, session_id: str) -> None:
        super().__init__(
            "session_not_found",
            f"No chat session with id '{session_id}'.",
        )


class AgentNotFoundError(ChatServiceError):
    def __init__(self, slug: str) -> None:
        super().__init__(
            "agent_not_found",
            f"No agent with slug '{slug}'.",
        )


class NoDefaultModelError(ChatServiceError):
    def __init__(self) -> None:
        super().__init__(
            "model_config_not_found",
            "No model config is currently marked as default.",
        )


async def create_session(
    client: AsyncClient,
    req: SessionCreateRequest,
) -> SessionDetail:
    agent_row = await _fetch_agent_by_slug(client, req.agent_slug)
    if agent_row is None:
        raise AgentNotFoundError(req.agent_slug)

    insert_data: dict[str, Any] = {
        "agent_id": agent_row["id"],
        "title": req.title,
        "model_config_id": req.model_config_id,
    }
    resp = await client.table("chat_sessions").insert(insert_data).execute()
    created = (resp.data or [{}])[0]
    return SessionDetail(
        id=str(created["id"]),
        agent_slug=agent_row["slug"],
        agent_name=agent_row["name"],
        title=created.get("title"),
        model_config_id=_str_or_none(created.get("model_config_id")),
        created_at=str(created.get("created_at", "")),
        updated_at=str(created.get("updated_at", "")),
        messages=[],
    )


async def list_sessions(client: AsyncClient) -> list[SessionListItem]:
    resp = await (
        client.table("chat_sessions")
        .select("id,agent_id,title,created_at,updated_at")
        .order("created_at")
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return []
    agent_ids = list({r["agent_id"] for r in rows})
    agents_resp = await (
        client.table("agents")
        .select("id,slug,name")
        .in_("id", agent_ids)
        .execute()
    )
    agent_lookup = {a["id"]: a for a in (agents_resp.data or [])}
    items: list[SessionListItem] = []
    for r in rows:
        agent = agent_lookup.get(r["agent_id"], {})
        items.append(
            SessionListItem(
                id=str(r["id"]),
                agent_slug=agent.get("slug", ""),
                agent_name=agent.get("name", ""),
                title=r.get("title"),
                created_at=str(r.get("created_at", "")),
                updated_at=str(r.get("updated_at", "")),
            )
        )
    return items


async def get_session(
    client: AsyncClient,
    session_id: str,
) -> SessionDetail | None:
    session_row = await _fetch_session_row(client, session_id)
    if session_row is None:
        return None
    agent_resp = await (
        client.table("agents")
        .select("slug,name")
        .eq("id", session_row["agent_id"])
        .maybe_single()
        .execute()
    )
    agent = agent_resp.data or {}
    msg_resp = await (
        client.table("chat_messages")
        .select("id,role,content,finish_reason,created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    messages = [
        ChatMessage(
            id=str(m["id"]),
            role=m["role"],
            content=m.get("content"),
            finish_reason=m.get("finish_reason"),
            created_at=str(m.get("created_at", "")),
        )
        for m in (msg_resp.data or [])
    ]
    return SessionDetail(
        id=str(session_row["id"]),
        agent_slug=agent.get("slug", ""),
        agent_name=agent.get("name", ""),
        title=session_row.get("title"),
        model_config_id=_str_or_none(session_row.get("model_config_id")),
        created_at=str(session_row.get("created_at", "")),
        updated_at=str(session_row.get("updated_at", "")),
        messages=messages,
    )


async def delete_session(client: AsyncClient, session_id: str) -> bool:
    existing = await _fetch_session_row(client, session_id)
    if existing is None:
        return False
    await (
        client.table("chat_sessions")
        .delete()
        .eq("id", session_id)
        .execute()
    )
    return True


async def prepare_stream(
    client: AsyncClient,
    session_id: str,
    content: str,
    *,
    streamer: ChatStreamer | None = None,
) -> AsyncIterator[str]:
    session_row = await _fetch_session_row(client, session_id)
    if session_row is None:
        raise SessionNotFoundError(session_id)

    agent_resp = await (
        client.table("agents")
        .select("system_prompt")
        .eq("id", session_row["agent_id"])
        .maybe_single()
        .execute()
    )
    agent_row = agent_resp.data or {}
    system_prompt = agent_row.get("system_prompt", "")

    model_row = await _fetch_runtime_model_config(
        client, session_row.get("model_config_id")
    )
    if model_row is None:
        raise NoDefaultModelError()

    user_msg_resp = await (
        client.table("chat_messages")
        .insert(
            {
                "session_id": session_id,
                "role": "user",
                "content": content,
            }
        )
        .execute()
    )
    user_msg = (user_msg_resp.data or [{}])[0]
    user_message_id = str(user_msg.get("id", ""))

    history = await _load_history(client, session_id)
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)

    config = LLMStreamConfig(
        base_url=model_row["base_url"],
        api_key=model_row["api_key"],
        model_name=model_row["model_name"],
        temperature=float(model_row.get("temperature", 0.70)),
        max_tokens=model_row.get("max_tokens"),
    )

    return _stream_with_persistence(
        client=client,
        session_id=session_id,
        user_message_id=user_message_id,
        config=config,
        messages=messages,
        streamer=streamer or http_stream_chat_completion,
    )


async def _stream_with_persistence(
    *,
    client: AsyncClient,
    session_id: str,
    user_message_id: str,
    config: LLMStreamConfig,
    messages: list[dict[str, Any]],
    streamer: ChatStreamer,
) -> AsyncIterator[str]:
    yield _sse(
        "message_start",
        {"message_id": user_message_id, "session_id": session_id},
    )

    accumulated: list[str] = []
    finish_reason: str | None = None
    error_event: StreamEvent | None = None

    try:
        async for ev in streamer(config, messages):
            if ev.type == "token":
                accumulated.append(ev.text)
                yield _sse("token", {"delta": ev.text})
            elif ev.type == "complete":
                finish_reason = ev.finish_reason
            elif ev.type == "error":
                error_event = ev
                break
    except Exception as exc:
        error_event = StreamEvent(
            type="error",
            error_code="stream_failed",
            text=f"{type(exc).__name__}",
        )

    if error_event is not None:
        yield _sse(
            "error",
            {
                "code": error_event.error_code or "stream_failed",
                "message": error_event.text,
                "recoverable": False,
            },
        )
        yield _sse("done", {})
        return

    assistant_text = "".join(accumulated)
    assistant_resp = await (
        client.table("chat_messages")
        .insert(
            {
                "session_id": session_id,
                "role": "assistant",
                "content": assistant_text,
                "finish_reason": finish_reason or "stop",
            }
        )
        .execute()
    )
    assistant_row = (assistant_resp.data or [{}])[0]
    assistant_message_id = str(assistant_row.get("id", ""))

    yield _sse(
        "message_complete",
        {
            "message_id": assistant_message_id,
            "finish_reason": finish_reason or "stop",
        },
    )
    yield _sse("done", {})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _str_or_none(val: Any) -> str | None:
    return str(val) if val is not None else None


async def _fetch_agent_by_slug(
    client: AsyncClient, slug: str
) -> dict[str, Any] | None:
    resp = await (
        client.table("agents")
        .select("id,slug,name")
        .eq("slug", slug)
        .maybe_single()
        .execute()
    )
    return resp.data


async def _fetch_session_row(
    client: AsyncClient, session_id: str
) -> dict[str, Any] | None:
    resp = await (
        client.table("chat_sessions")
        .select("*")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    return resp.data


async def _fetch_runtime_model_config(
    client: AsyncClient,
    explicit_id: str | None,
) -> dict[str, Any] | None:
    if explicit_id:
        resp = await (
            client.table("model_configs")
            .select("base_url,api_key,model_name,temperature,max_tokens")
            .eq("id", explicit_id)
            .maybe_single()
            .execute()
        )
        if resp.data:
            return resp.data
    resp = await (
        client.table("model_configs")
        .select("base_url,api_key,model_name,temperature,max_tokens")
        .eq("is_default", True)
        .maybe_single()
        .execute()
    )
    return resp.data


async def _load_history(
    client: AsyncClient, session_id: str
) -> list[dict[str, Any]]:
    resp = await (
        client.table("chat_messages")
        .select("role,content")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    rows = resp.data or []
    return [
        {"role": r["role"], "content": r.get("content") or ""}
        for r in rows
    ]
