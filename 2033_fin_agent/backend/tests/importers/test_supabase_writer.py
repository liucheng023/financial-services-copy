"""Unit tests for the Supabase writer.

The writer talks to ``supabase-py`` through a tiny surface — ``client.table(name)
.upsert(rows, on_conflict=...).execute()`` and ``client.table(name).select(...)
.execute()``. We mock that surface to assert:

* the right ``on_conflict`` key is used per table (idempotency contract),
* FK lookups go through the right select(),
* unmatched agent_mcp candidates are skipped, not written,
* ``api_key`` is never invented when the upstream record lacks one,
* a second run with the same input produces the same upsert payload (call
  parity = idempotency at the wire level — Supabase's own ON CONFLICT
  semantics then make it a no-op at the row level).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.importers.agent_parser import ParsedAgent
from app.importers.associations import AgentMcpCandidate
from app.importers.mcp_parser import ParsedMcpServer
from app.importers.skill_parser import ParsedSkill
from app.importers.supabase_writer import (
    SupabaseEnvMissingError,
    build_client,
    upsert_agent_mcps,
    upsert_agents,
    upsert_mcp_servers,
    upsert_skills,
    upsert_vertical_mcps,
    upsert_vertical_skills,
    upsert_verticals,
)
from app.importers.vertical_parser import ParsedVertical


@dataclass
class _RecordedCall:
    table: str
    op: str
    args: tuple
    kwargs: dict


class _FakeExecResult:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, table: str, recorder: list[_RecordedCall], select_data: list[dict]):
        self._table = table
        self._recorder = recorder
        self._select_data = select_data

    def upsert(self, rows: list[dict], *, on_conflict: str | None = None) -> _FakeQuery:
        self._recorder.append(
            _RecordedCall(self._table, "upsert", (rows,), {"on_conflict": on_conflict})
        )
        return self

    def select(self, cols: str) -> _FakeQuery:
        self._recorder.append(_RecordedCall(self._table, "select", (cols,), {}))
        return self

    def execute(self) -> _FakeExecResult:
        return _FakeExecResult(self._select_data)


class FakeClient:
    """Minimal supabase-py-shaped fake.

    ``select_data_by_table`` lets each test pre-seed the rows that a
    ``.select("id,slug")`` would return for FK lookups.
    """

    def __init__(self, select_data_by_table: dict[str, list[dict]] | None = None) -> None:
        self.calls: list[_RecordedCall] = []
        self._select_data = select_data_by_table or {}

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name, self.calls, self._select_data.get(name, []))


def _upserts_for(client: FakeClient, table: str) -> list[_RecordedCall]:
    return [c for c in client.calls if c.table == table and c.op == "upsert"]


def test_build_client_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(SupabaseEnvMissingError):
        build_client()


def test_upsert_verticals_uses_slug_conflict_key() -> None:
    client = FakeClient()
    verticals = [
        ParsedVertical(slug="x", name="X", description="d", raw_manifest={"k": "v"}),
    ]
    n = upsert_verticals(client, verticals)
    assert n == 1
    [call] = _upserts_for(client, "verticals")
    assert call.kwargs == {"on_conflict": "slug"}
    [row] = call.args[0]
    assert row == {"slug": "x", "name": "X", "description": "d", "raw_manifest": {"k": "v"}}


def test_upsert_agents_uses_slug_conflict_key() -> None:
    client = FakeClient()
    agent = ParsedAgent(
        slug="pitch-agent",
        name="Pitch",
        description="d",
        system_prompt="sp",
        workflow="wf",
        guardrails="g",
        outputs="o",
        raw_frontmatter={"name": "Pitch"},
    )
    n = upsert_agents(client, [agent])
    assert n == 1
    [call] = _upserts_for(client, "agents")
    assert call.kwargs == {"on_conflict": "slug"}


def test_upsert_mcp_servers_never_writes_api_key() -> None:
    client = FakeClient()
    mcp = ParsedMcpServer(
        slug="s-and-p-global",
        name="S&P Global",
        url="https://example.test/mcp",
        transport="http",
        description=None,
        tool_name_map={"capiq": "s-and-p-global"},
        raw_manifest={"x": 1},
        source_path="plugins/vertical-plugins/financial-analysis/.mcp.json",
    )
    upsert_mcp_servers(client, [mcp])
    [call] = _upserts_for(client, "mcp_servers")
    [row] = call.args[0]
    assert "api_key" not in row, "writer must NEVER invent an api_key column value"


def test_upsert_skills_resolves_vertical_id_via_lookup() -> None:
    client = FakeClient(
        select_data_by_table={
            "verticals": [
                {"id": "vid-fa", "slug": "financial-analysis"},
                {"id": "vid-other", "slug": "other"},
            ]
        }
    )
    skills = [
        ParsedSkill(
            slug="dcf-model",
            name="DCF",
            description=None,
            vertical_slug="financial-analysis",
            content="...",
            raw_frontmatter={"name": "DCF"},
        ),
        ParsedSkill(
            slug="orphan",
            name="Orphan",
            description=None,
            vertical_slug=None,
            content="...",
            raw_frontmatter={"name": "Orphan"},
        ),
    ]
    n = upsert_skills(client, skills)
    assert n == 2
    [call] = _upserts_for(client, "skills")
    rows = call.args[0]
    rows_by_slug = {r["slug"]: r for r in rows}
    assert rows_by_slug["dcf-model"]["vertical_id"] == "vid-fa"
    assert rows_by_slug["orphan"]["vertical_id"] is None


def test_upsert_vertical_skills_uses_composite_conflict_key() -> None:
    client = FakeClient(
        select_data_by_table={
            "verticals": [{"id": "v1", "slug": "fa"}],
            "skills": [{"id": "s1", "slug": "dcf"}, {"id": "s2", "slug": "comps"}],
        }
    )
    n = upsert_vertical_skills(client, [("fa", "dcf"), ("fa", "comps"), ("fa", "missing")])
    assert n == 2
    [call] = _upserts_for(client, "vertical_skills")
    assert call.kwargs == {"on_conflict": "vertical_id,skill_id"}


def test_upsert_vertical_mcps_uses_composite_conflict_key() -> None:
    client = FakeClient(
        select_data_by_table={
            "verticals": [{"id": "v1", "slug": "fa"}],
            "mcp_servers": [{"id": "m1", "slug": "factset"}],
        }
    )
    n = upsert_vertical_mcps(client, [("fa", "factset")])
    assert n == 1
    [call] = _upserts_for(client, "vertical_mcps")
    assert call.kwargs == {"on_conflict": "vertical_id,mcp_server_id"}


def test_upsert_agent_mcps_skips_unmatched_and_dedupes() -> None:
    client = FakeClient(
        select_data_by_table={
            "agents": [{"id": "a1", "slug": "pitch-agent"}],
            "mcp_servers": [{"id": "m1", "slug": "s-and-p-global"}],
        }
    )
    candidates = [
        AgentMcpCandidate("pitch-agent", "capiq", "s-and-p-global", "aliased"),
        AgentMcpCandidate("pitch-agent", "s-and-p-global", "s-and-p-global", "matched"),
        AgentMcpCandidate("pitch-agent", "internal-gl", None, "unmatched"),
    ]
    written, skipped = upsert_agent_mcps(client, candidates)
    assert written == 1
    assert skipped == 1
    [call] = _upserts_for(client, "agent_mcps")
    assert call.kwargs == {"on_conflict": "agent_id,mcp_server_id"}


def test_idempotent_second_call_produces_same_payload() -> None:
    verticals = [ParsedVertical("x", "X", "d", {"k": "v"})]
    c1 = FakeClient()
    c2 = FakeClient()
    upsert_verticals(c1, verticals)
    upsert_verticals(c2, verticals)
    assert _upserts_for(c1, "verticals")[0].args == _upserts_for(c2, "verticals")[0].args


def test_empty_input_writes_nothing() -> None:
    client = FakeClient()
    assert upsert_verticals(client, []) == 0
    assert upsert_agents(client, []) == 0
    assert upsert_mcp_servers(client, []) == 0
    assert _upserts_for(client, "verticals") == []
