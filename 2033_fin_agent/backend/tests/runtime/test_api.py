"""Tests for the Task 5 read-only + MCP write APIs.

Uses a mock Supabase AsyncClient injected via FastAPI dependency override.
Tests cover:

* GET /api/agents — list
* GET /api/agents/{slug} — detail with skills + mcps
* GET /api/verticals — list
* GET /api/verticals/{slug} — detail with skills + mcps
* GET /api/mcp-servers — list (no api_key in response)
* GET /api/mcp-servers/{id} — detail (masked_api_key, no plaintext)
* POST /api/mcp-servers — requires admin token
* PUT /api/mcp-servers/{id} — requires admin token
* 404 error codes: agent_not_found, vertical_not_found, mcp_server_not_found
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.supabase import get_supabase

FAKE_AGENT_ROW = {
    "id": "a1",
    "slug": "pitch-agent",
    "name": "Pitch Agent",
    "description": "Writes pitch decks",
    "system_prompt": "You are a pitch agent.",
    "workflow": "Gather data -> draft -> polish",
    "guardrails": "Never fabricate numbers",
    "outputs": "PPTX + XLSX",
}

FAKE_SKILL_ROW = {
    "id": "s1",
    "slug": "dcf-model",
    "name": "DCF Model",
    "description": "Discounted cash flow analysis",
}

FAKE_MCP_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "factset",
    "name": "FactSet",
    "url": "https://mcp.factset.com/mcp",
    "transport": "http",
    "description": "FactSet data",
    "api_key": "sk-factset-abcdef1234",
    "tool_name_map": {},
}

FAKE_MCP_ROW_NO_KEY = {
    "id": "22222222-2222-2222-2222-222222222222",
    "slug": "daloopa",
    "name": "Daloopa",
    "url": "https://mcp.daloopa.com/server/mcp",
    "transport": "http",
    "description": None,
    "api_key": None,
    "tool_name_map": {},
}

FAKE_VERTICAL_ROW = {
    "id": "v1",
    "slug": "financial-analysis",
    "name": "Financial Analysis",
    "description": "Core modeling skills",
}

TABLES = {
    "agents": [FAKE_AGENT_ROW],
    "verticals": [FAKE_VERTICAL_ROW],
    "skills": [FAKE_SKILL_ROW],
    "mcp_servers": [FAKE_MCP_ROW, FAKE_MCP_ROW_NO_KEY],
    "agent_skills": [{"agent_id": "a1", "skill_id": "s1"}],
    "agent_mcps": [
        {"agent_id": "a1", "mcp_server_id": "11111111-1111-1111-1111-111111111111"},
    ],
    "vertical_skills": [{"vertical_id": "v1", "skill_id": "s1"}],
    "vertical_mcps": [
        {"vertical_id": "v1", "mcp_server_id": "11111111-1111-1111-1111-111111111111"},
    ],
}


class _FakeResult:
    def __init__(self, data: list[dict] | dict | None = None) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, table: str, rows: list[dict]) -> None:
        self._table = table
        self._rows = list(rows)
        self._filters: list[tuple[str, str]] = []
        self._in_filters: list[tuple[str, list[str]]] = []
        self._is_single = False
        self._insert_data: dict | None = None
        self._update_data: dict | None = None

    def select(self, _cols: str) -> _FakeQuery:
        return self

    def eq(self, col: str, val: str) -> _FakeQuery:
        self._filters.append((col, val))
        return self

    def in_(self, col: str, vals: list[str]) -> _FakeQuery:
        self._in_filters.append((col, vals))
        return self

    def order(self, _field: str) -> _FakeQuery:
        return self

    def maybe_single(self) -> _FakeQuery:
        self._is_single = True
        return self

    def insert(self, data: dict) -> _FakeQuery:
        self._insert_data = data
        return self

    def update(self, data: dict) -> _FakeQuery:
        self._update_data = data
        return self

    async def execute(self) -> _FakeResult:
        if self._insert_data:
            row = {"id": "new-id", **self._insert_data}
            return _FakeResult([row])

        filtered = list(self._rows)

        for col, val in self._in_filters:
            filtered = [r for r in filtered if r.get(col) in val]

        for col, val in self._filters:
            filtered = [r for r in filtered if str(r.get(col)) == val]

        if self._update_data:
            if filtered:
                merged = {**filtered[0], **self._update_data}
                return _FakeResult([merged])
            return _FakeResult([])

        if self._is_single:
            return _FakeResult(filtered[0] if filtered else None)

        return _FakeResult(filtered)


class FakeAsyncClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name, self._tables.get(name, []))


@pytest.fixture
def api_client(env_setup) -> TestClient:
    from app.core.supabase import _reset_client_sync

    _reset_client_sync()
    mock = FakeAsyncClient(TABLES)

    async def _override():
        return mock

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_supabase] = _override
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.clear()
    _reset_client_sync()


ADMIN_HEADERS = {"X-Admin-Token": "admin-token-test-value"}


def test_list_agents(api_client: TestClient) -> None:
    resp = api_client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    agent = data[0]
    assert agent["slug"] == "pitch-agent"
    assert "skill_count" in agent
    assert "mcp_count" in agent


def test_get_agent_detail(api_client: TestClient) -> None:
    resp = api_client.get("/api/agents/pitch-agent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "pitch-agent"
    assert data["system_prompt"] == "You are a pitch agent."
    assert "skills" in data
    assert "mcps" in data
    assert data["workflow"] is not None


def test_get_agent_not_found(api_client: TestClient) -> None:
    resp = api_client.get("/api/agents/nonexistent")
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["code"] == "agent_not_found"
    assert body["type"] == "about:blank"
    assert body["status"] == 404


def test_list_verticals(api_client: TestClient) -> None:
    resp = api_client.get("/api/verticals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["slug"] == "financial-analysis"


def test_get_vertical_detail(api_client: TestClient) -> None:
    resp = api_client.get("/api/verticals/financial-analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "financial-analysis"
    assert "skills" in data
    assert "mcps" in data


def test_get_vertical_not_found(api_client: TestClient) -> None:
    resp = api_client.get("/api/verticals/nonexistent")
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["code"] == "vertical_not_found"


def test_list_mcp_servers_no_api_key(api_client: TestClient) -> None:
    resp = api_client.get("/api/mcp-servers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for item in data:
        assert "api_key" not in item
        assert "has_api_key" in item


def test_get_mcp_server_detail_masked_key(api_client: TestClient) -> None:
    resp = api_client.get("/api/mcp-servers/11111111-1111-1111-1111-111111111111")
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" not in data
    assert data["has_api_key"] is True
    assert data["masked_api_key"] == "****1234"
    assert "sk-factset" not in resp.text


def test_get_mcp_server_detail_no_key(api_client: TestClient) -> None:
    resp = api_client.get("/api/mcp-servers/22222222-2222-2222-2222-222222222222")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_api_key"] is False
    assert data["masked_api_key"] is None


def test_get_mcp_server_not_found(api_client: TestClient) -> None:
    resp = api_client.get("/api/mcp-servers/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["code"] == "mcp_server_not_found"


def test_create_mcp_server_requires_admin(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/mcp-servers",
        json={"slug": "x", "name": "X", "url": "https://x"},
    )
    assert resp.status_code == 401


def test_create_mcp_server_with_admin(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/mcp-servers",
        json={
            "slug": "new-mcp",
            "name": "New MCP",
            "url": "https://new.mcp/test",
            "api_key": "sk-test-key-abc",
        },
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "new-mcp"
    assert "api_key" not in data
    assert data["has_api_key"] is True
    assert "sk-test-key-abc" not in resp.text


def test_update_mcp_server_requires_admin(api_client: TestClient) -> None:
    resp = api_client.put(
        "/api/mcp-servers/11111111-1111-1111-1111-111111111111",
        json={"name": "Updated"},
    )
    assert resp.status_code == 401


def test_update_mcp_server_with_admin(api_client: TestClient) -> None:
    resp = api_client.put(
        "/api/mcp-servers/11111111-1111-1111-1111-111111111111",
        json={"name": "Updated FactSet"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated FactSet"
