from __future__ import annotations

from typing import Any

from app.adapters.mcp_adapter import MCPToolset
from app.services import mcp_service
from tests.runtime.test_api import TABLES, FakeAsyncClient


class _NoopMCPClient:
    async def close_all_sessions(self) -> None:
        return None


class _NoopOpenAIAdapter:
    tools: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []
    tool_executors: dict[str, Any] = {}

    async def create_all(self, client: _NoopMCPClient) -> None:
        return None

    def parse_result(self, result: Any) -> str:
        return str(result)


async def test_list_agent_mcp_configs_loads_agent_bound_servers() -> None:
    client = FakeAsyncClient(TABLES)

    configs = await mcp_service.list_agent_mcp_configs(client, "pitch-agent")

    assert len(configs) == 1
    config = configs[0]
    assert config.slug == "factset"
    assert config.name == "FactSet"
    assert config.url == "https://mcp.factset.com/mcp"
    assert config.transport == "http"
    assert config.api_key == "sk-factset-abcdef1234"


async def test_list_agent_mcp_configs_unknown_agent_returns_empty() -> None:
    client = FakeAsyncClient(TABLES)

    configs = await mcp_service.list_agent_mcp_configs(client, "missing-agent")

    assert configs == []


async def test_create_agent_mcp_toolset_uses_loaded_configs(monkeypatch) -> None:
    client = FakeAsyncClient(TABLES)
    captured_slugs: list[str] = []

    async def fake_create_openai_toolset(configs):
        captured_slugs.extend(config.slug for config in configs)
        return MCPToolset(client=_NoopMCPClient(), adapter=_NoopOpenAIAdapter(), tools=[])

    monkeypatch.setattr(mcp_service, "create_openai_toolset", fake_create_openai_toolset)

    toolset = await mcp_service.create_agent_mcp_toolset(client, "pitch-agent")

    assert captured_slugs == ["factset"]
    assert toolset.tools == []
