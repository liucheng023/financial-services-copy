from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MCPClientProtocol(Protocol):
    async def close_all_sessions(self) -> None: ...


class OpenAIAdapterProtocol(Protocol):
    tools: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    prompts: list[dict[str, Any]]
    tool_executors: dict[str, Any]

    async def create_all(self, client: MCPClientProtocol) -> None: ...

    def parse_result(self, result: Any) -> str: ...


@dataclass(frozen=True)
class MCPServerConfig:
    slug: str
    name: str
    url: str
    transport: str = "http"
    api_key: str | None = None
    tool_name_map: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPToolset:
    client: MCPClientProtocol
    adapter: OpenAIAdapterProtocol
    tools: list[dict[str, Any]]
    failed_servers: list[str] = field(default_factory=list)

    async def close(self) -> None:
        await self.client.close_all_sessions()


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    content: str
    is_error: bool = False


def build_mcp_use_config(servers: list[MCPServerConfig]) -> dict[str, dict[str, dict[str, Any]]]:
    mcp_servers: dict[str, dict[str, Any]] = {}
    for server in servers:
        headers: dict[str, str] = {}
        if server.api_key:
            headers["Authorization"] = f"Bearer {server.api_key}"

        server_config: dict[str, Any] = {
            "url": server.url,
            "transport": server.transport,
        }
        if headers:
            server_config["headers"] = headers
        mcp_servers[server.slug] = server_config
    return {"mcpServers": mcp_servers}


def _load_mcp_use_classes() -> tuple[type, type]:
    from mcp_use import MCPClient
    from mcp_use.agents.adapters import OpenAIMCPAdapter

    return MCPClient, OpenAIMCPAdapter


async def create_openai_toolset(
    servers: list[MCPServerConfig],
    *,
    client_cls: type | None = None,
    adapter_cls: type | None = None,
) -> MCPToolset:
    if client_cls is None or adapter_cls is None:
        loaded_client_cls, loaded_adapter_cls = _load_mcp_use_classes()
        client_cls = client_cls or loaded_client_cls
        adapter_cls = adapter_cls or loaded_adapter_cls

    config = build_mcp_use_config(servers)
    client = client_cls(config=config)
    adapter = adapter_cls()
    failed_servers: list[str] = []

    try:
        await adapter.create_all(client)
    except Exception as exc:
        failed_servers = [server.slug for server in servers]
        logger.warning(
            "MCP tool initialization failed; continuing without MCP tools",
            extra={"mcp_servers": failed_servers, "error_type": type(exc).__name__},
        )
        await _close_client_safely(client)
        return MCPToolset(client=client, adapter=adapter, tools=[], failed_servers=failed_servers)

    tools = list(adapter.tools) + list(adapter.resources) + list(adapter.prompts)
    return MCPToolset(client=client, adapter=adapter, tools=tools, failed_servers=failed_servers)


async def execute_tool_call(
    toolset: MCPToolset,
    tool_name: str,
    arguments: dict[str, Any],
) -> ToolExecutionResult:
    executor = toolset.adapter.tool_executors.get(tool_name)
    if executor is None:
        return ToolExecutionResult(
            tool_name=tool_name,
            content=f"Error: Tool '{tool_name}' not found.",
            is_error=True,
        )

    try:
        raw_result = await executor(**arguments)
        return ToolExecutionResult(
            tool_name=tool_name,
            content=toolset.adapter.parse_result(raw_result),
            is_error=False,
        )
    except Exception as exc:
        logger.warning(
            "MCP tool execution failed",
            extra={"tool_name": tool_name, "error_type": type(exc).__name__},
        )
        return ToolExecutionResult(
            tool_name=tool_name,
            content=f"Error executing tool: {type(exc).__name__}",
            is_error=True,
        )


async def _close_client_safely(client: MCPClientProtocol) -> None:
    try:
        await client.close_all_sessions()
    except Exception as exc:
        logger.warning(
            "MCP client cleanup failed",
            extra={"error_type": type(exc).__name__},
        )
