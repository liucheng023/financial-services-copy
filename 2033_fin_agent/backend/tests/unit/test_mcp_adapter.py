from __future__ import annotations

import pytest

from app.adapters.mcp_adapter import (
    MCPServerConfig,
    build_mcp_use_config,
    create_openai_toolset,
    execute_tool_call,
)


class FakeMCPClient:
    instances: list[FakeMCPClient] = []

    def __init__(self, config: dict) -> None:
        self.config = config
        self.closed = False
        FakeMCPClient.instances.append(self)

    async def close_all_sessions(self) -> None:
        self.closed = True


class FakeOpenAIAdapter:
    should_fail_create = False

    def __init__(self) -> None:
        self.tools = [
            {"type": "function", "function": {"name": "lookup_company", "parameters": {}}},
        ]
        self.resources = []
        self.prompts = []
        self.tool_executors = {"lookup_company": self.lookup_company}
        self.created = False

    async def create_all(self, client: FakeMCPClient) -> None:
        self.created = True
        if self.should_fail_create:
            raise RuntimeError("connect failed")

    async def lookup_company(self, ticker: str) -> dict[str, str]:
        return {"ticker": ticker, "name": "Example Co"}

    def parse_result(self, result: dict[str, str]) -> str:
        return f"{result['ticker']}:{result['name']}"


class FailingToolAdapter(FakeOpenAIAdapter):
    async def lookup_company(self, ticker: str) -> dict[str, str]:
        raise RuntimeError("provider failed")


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeMCPClient.instances.clear()
    FakeOpenAIAdapter.should_fail_create = False


def test_build_mcp_use_config_includes_auth_header_without_exposing_key_name() -> None:
    config = build_mcp_use_config(
        [
            MCPServerConfig(
                slug="factset",
                name="FactSet",
                url="https://mcp.factset.com/mcp",
                transport="http",
                api_key="secret-token",
            ),
            MCPServerConfig(
                slug="daloopa",
                name="Daloopa",
                url="https://mcp.daloopa.com/server/mcp",
                transport="http",
            ),
        ]
    )

    assert config == {
        "mcpServers": {
            "factset": {
                "url": "https://mcp.factset.com/mcp",
                "transport": "http",
                "headers": {"Authorization": "Bearer secret-token"},
            },
            "daloopa": {
                "url": "https://mcp.daloopa.com/server/mcp",
                "transport": "http",
            },
        }
    }


async def test_create_openai_toolset_returns_tools_and_executor_map() -> None:
    toolset = await create_openai_toolset(
        [MCPServerConfig(slug="factset", name="FactSet", url="https://mcp.factset.com/mcp")],
        client_cls=FakeMCPClient,
        adapter_cls=FakeOpenAIAdapter,
    )

    assert len(toolset.tools) == 1
    assert toolset.tools[0]["function"]["name"] == "lookup_company"
    assert toolset.failed_servers == []
    assert FakeMCPClient.instances[0].config["mcpServers"]["factset"]["url"].startswith("https://")

    result = await execute_tool_call(toolset, "lookup_company", {"ticker": "MSFT"})
    assert result.is_error is False
    assert result.content == "MSFT:Example Co"

    await toolset.close()
    assert FakeMCPClient.instances[0].closed is True


async def test_create_openai_toolset_gracefully_degrades_on_init_failure() -> None:
    FakeOpenAIAdapter.should_fail_create = True

    toolset = await create_openai_toolset(
        [MCPServerConfig(slug="factset", name="FactSet", url="https://mcp.factset.com/mcp")],
        client_cls=FakeMCPClient,
        adapter_cls=FakeOpenAIAdapter,
    )

    assert toolset.tools == []
    assert toolset.failed_servers == ["factset"]
    assert FakeMCPClient.instances[0].closed is True


async def test_execute_tool_call_handles_unknown_tool() -> None:
    toolset = await create_openai_toolset(
        [MCPServerConfig(slug="factset", name="FactSet", url="https://mcp.factset.com/mcp")],
        client_cls=FakeMCPClient,
        adapter_cls=FakeOpenAIAdapter,
    )

    result = await execute_tool_call(toolset, "missing_tool", {})

    assert result.is_error is True
    assert result.content == "Error: Tool 'missing_tool' not found."


async def test_execute_tool_call_redacts_provider_exception_message() -> None:
    toolset = await create_openai_toolset(
        [MCPServerConfig(slug="factset", name="FactSet", url="https://mcp.factset.com/mcp")],
        client_cls=FakeMCPClient,
        adapter_cls=FailingToolAdapter,
    )

    result = await execute_tool_call(toolset, "lookup_company", {"ticker": "MSFT"})

    assert result.is_error is True
    assert result.content == "Error executing tool: RuntimeError"
    assert "provider failed" not in result.content
