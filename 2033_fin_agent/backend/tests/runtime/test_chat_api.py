from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.supabase import get_supabase

AGENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
AGENT_SLUG = "pitch-agent"
AGENT_NAME = "Pitch Agent"

MODEL_ID = "11111111-1111-1111-1111-111111111111"
MODEL_API_KEY = "sk-glm-secret-tail9999"
MODEL_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"

EXISTING_SESSION_ID = "33333333-3333-3333-3333-333333333333"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _initial_state() -> dict[str, list[dict[str, Any]]]:
    return {
        "agents": [
            {
                "id": AGENT_ID,
                "slug": AGENT_SLUG,
                "name": AGENT_NAME,
                "system_prompt": "You are a financial pitch expert.",
            }
        ],
        "model_configs": [
            {
                "id": MODEL_ID,
                "slug": "zhipu-coding-glm-51",
                "name": "GLM-5.1",
                "base_url": MODEL_BASE_URL,
                "api_key": MODEL_API_KEY,
                "model_name": "GLM-5.1",
                "temperature": 0.7,
                "max_tokens": 4096,
                "is_default": True,
            }
        ],
        "chat_sessions": [
            {
                "id": EXISTING_SESSION_ID,
                "agent_id": AGENT_ID,
                "model_config_id": None,
                "title": "Existing session",
                "created_at": _now(),
                "updated_at": _now(),
            }
        ],
        "chat_messages": [],
    }


class _Result:
    def __init__(self, data: Any) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._eq: list[tuple[str, Any]] = []
        self._in: list[tuple[str, list[Any]]] = []
        self._single = False
        self._insert: dict[str, Any] | None = None
        self._update: dict[str, Any] | None = None
        self._delete = False

    def select(self, _cols: str, **_kwargs: Any) -> _Query:
        return self

    def order(self, _field: str) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self._eq.append((col, val))
        return self

    def in_(self, col: str, vals: list[Any]) -> _Query:
        self._in.append((col, vals))
        return self

    def maybe_single(self) -> _Query:
        self._single = True
        return self

    def insert(self, data: dict[str, Any]) -> _Query:
        self._insert = data
        return self

    def update(self, data: dict[str, Any]) -> _Query:
        self._update = data
        return self

    def delete(self) -> _Query:
        self._delete = True
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        for col, val in self._eq:
            if row.get(col) != val:
                return False
        return all(row.get(col) in vals for col, vals in self._in)

    async def execute(self) -> _Result:
        if self._insert is not None:
            new_id = f"new-{len(self._rows) + 1}"
            row = {
                "id": new_id,
                "created_at": _now(),
                "updated_at": _now(),
                **self._insert,
            }
            self._rows.append(row)
            return _Result([row])

        matched = [r for r in self._rows if self._match(r)]

        if self._delete:
            for r in matched:
                self._rows.remove(r)
            return _Result(matched)

        if self._update is not None:
            for r in matched:
                r.update(self._update)
            return _Result(matched)

        if self._single:
            return _Result(matched[0] if matched else None)
        return _Result(matched)


class FakeAsyncClient:
    def __init__(self, state: dict[str, list[dict[str, Any]]]) -> None:
        self._state = state

    def table(self, name: str) -> _Query:
        if name not in self._state:
            self._state[name] = []
        return _Query(self._state[name])


@pytest.fixture
def api_client(env_setup) -> TestClient:
    from app.core.supabase import _reset_client_sync

    _reset_client_sync()
    state = _initial_state()
    mock = FakeAsyncClient(state)

    async def _override():
        return mock

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_supabase] = _override
    tc = TestClient(app)
    tc.fake_state = state
    yield tc
    app.dependency_overrides.clear()
    _reset_client_sync()


def test_create_session_success(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/sessions",
        json={"agent_slug": AGENT_SLUG, "title": "My pitch"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_slug"] == AGENT_SLUG
    assert data["agent_name"] == AGENT_NAME
    assert data["title"] == "My pitch"
    assert data["messages"] == []
    assert data["id"]


def test_create_session_agent_not_found(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/sessions",
        json={"agent_slug": "no-such-agent"},
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["code"] == "agent_not_found"


def test_list_sessions(api_client: TestClient) -> None:
    resp = api_client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == EXISTING_SESSION_ID
    assert data[0]["agent_slug"] == AGENT_SLUG


def test_get_session_detail(api_client: TestClient) -> None:
    resp = api_client.get(f"/api/sessions/{EXISTING_SESSION_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == EXISTING_SESSION_ID
    assert data["agent_slug"] == AGENT_SLUG
    assert data["messages"] == []


def test_get_session_not_found(api_client: TestClient) -> None:
    missing = "99999999-9999-9999-9999-999999999999"
    resp = api_client.get(f"/api/sessions/{missing}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "session_not_found"


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = ""
        data_raw = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_raw = line[len("data:"):].strip()
        events.append((event_name, json.loads(data_raw) if data_raw else {}))
    return events


def test_send_message_streams_tokens_and_persists(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.adapters.llm_adapter import LLMStreamConfig, StreamEvent

    captured: dict[str, Any] = {}

    async def fake_stream(
        config: LLMStreamConfig, messages: list[dict[str, Any]]
    ) -> AsyncIterator[StreamEvent]:
        captured["config"] = config
        captured["messages"] = messages
        yield StreamEvent(type="token", text="Hello")
        yield StreamEvent(type="token", text=", ")
        yield StreamEvent(type="token", text="world!")
        yield StreamEvent(type="complete", finish_reason="stop")

    import app.services.chat_service as svc

    monkeypatch.setattr(svc, "http_stream_chat_completion", fake_stream)

    resp = api_client.post(
        f"/api/sessions/{EXISTING_SESSION_ID}/messages",
        json={"content": "Hi there"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    event_names = [e[0] for e in events]
    assert event_names[0] == "message_start"
    assert event_names.count("token") == 3
    assert "message_complete" in event_names
    assert event_names[-1] == "done"

    tokens = [e[1]["delta"] for e in events if e[0] == "token"]
    assert "".join(tokens) == "Hello, world!"

    start_evt = next(e[1] for e in events if e[0] == "message_start")
    complete = next(e[1] for e in events if e[0] == "message_complete")
    assert complete["finish_reason"] == "stop"
    assert start_evt["message_id"] == complete["message_id"]
    stable_message_id = start_evt["message_id"]
    assert stable_message_id

    config = captured["config"]
    assert config.base_url == MODEL_BASE_URL
    assert config.api_key == MODEL_API_KEY
    assert config.model_name == "GLM-5.1"

    sent = captured["messages"]
    assert sent[0]["role"] == "system"
    assert sent[0]["content"] == "You are a financial pitch expert."
    assert sent[-1]["role"] == "user"
    assert sent[-1]["content"] == "Hi there"
    assert all(
        not (m["role"] == "assistant" and m["content"] == "")
        for m in sent
    ), "assistant placeholder must not be sent to the LLM"

    persisted = api_client.fake_state["chat_messages"]
    assert len(persisted) == 2
    assert persisted[0]["role"] == "user"
    assert persisted[0]["content"] == "Hi there"
    assert persisted[1]["role"] == "assistant"
    assert persisted[1]["content"] == "Hello, world!"
    assert persisted[1]["finish_reason"] == "stop"
    assert str(persisted[1]["id"]) == stable_message_id

    assert MODEL_API_KEY not in resp.text


def test_send_message_session_not_found(api_client: TestClient) -> None:
    missing = "99999999-9999-9999-9999-999999999999"
    resp = api_client.post(
        f"/api/sessions/{missing}/messages",
        json={"content": "Hi"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "session_not_found"


def test_send_message_no_default_model(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for row in api_client.fake_state["model_configs"]:
        row["is_default"] = False

    resp = api_client.post(
        f"/api/sessions/{EXISTING_SESSION_ID}/messages",
        json={"content": "Hi"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "model_config_not_found"

    for row in api_client.fake_state["model_configs"]:
        row["is_default"] = True


def test_send_message_llm_error_emits_sse_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.adapters.llm_adapter import LLMStreamConfig, StreamEvent

    async def failing_stream(
        _config: LLMStreamConfig, _messages: list[dict[str, Any]]
    ) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="error", error_code="timeout", text="LLM timed out")

    import app.services.chat_service as svc

    monkeypatch.setattr(svc, "http_stream_chat_completion", failing_stream)

    resp = api_client.post(
        f"/api/sessions/{EXISTING_SESSION_ID}/messages",
        json={"content": "Hi"},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    event_names = [e[0] for e in events]
    assert "error" in event_names
    assert event_names[-1] == "done"

    start_evt = next(e[1] for e in events if e[0] == "message_start")
    assert start_evt["message_id"], "message_start must carry assistant message id"

    error_evt = next(e[1] for e in events if e[0] == "error")
    assert error_evt["code"] == "timeout"
    assert error_evt["recoverable"] is False

    assistant_rows = [
        m
        for m in api_client.fake_state["chat_messages"]
        if m["role"] == "assistant"
    ]
    assert len(assistant_rows) == 1
    assert assistant_rows[0]["finish_reason"] == "error"
    assert assistant_rows[0]["content"] == ""
    assert str(assistant_rows[0]["id"]) == start_evt["message_id"]

    assert MODEL_API_KEY not in resp.text
