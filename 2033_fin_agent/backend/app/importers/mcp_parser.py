"""Parse upstream MCP server configurations from .mcp.json files.

MCP configs are centralized in ``financial-analysis/.mcp.json``. Some other
verticals also have ``.mcp.json`` but typically with an empty MCP map; we
merge all discovered MCP entries and return them keyed by their slug.

Pure: no Supabase, no I/O beyond reading the given files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class McpParseError(ValueError):
    pass


# Known agent-facing aliases that differ from the MCP slug in .mcp.json.
# These are the only documented aliases across all 10 agent plugins.
_KNOWN_TOOL_NAME_ALIASES: dict[str, str] = {
    "capiq": "sp-global",
}


@dataclass(frozen=True)
class ParsedMcpServer:
    slug: str
    name: str
    url: str
    transport: str = "http"
    description: str | None = None
    tool_name_map: dict[str, str] = field(default_factory=dict)
    raw_manifest: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


def build_tool_name_map(slug: str, known_aliases: dict[str, str] | None = None) -> dict[str, str]:
    """Build tool-name mapping for an MCP slug.

    Returns a {user_facing_alias: mcp_slug} map. For example, if `capiq`
    is a known alias for `sp-global`, the map will be ``{"capiq": "sp-global"}``.
    """
    result: dict[str, str] = {}
    aliases = known_aliases or _KNOWN_TOOL_NAME_ALIASES
    for alias, canonical in aliases.items():
        if canonical == slug:
            result[alias] = slug
    return result


def parse_mcp_json(mcp_json_path: Path) -> list[ParsedMcpServer]:
    """Parse a .mcp.json file and return a list of ParsedMcpServer records."""
    if not mcp_json_path.is_file():
        return []

    try:
        data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise McpParseError(f"invalid JSON in {mcp_json_path}: {exc}") from exc

    mcp_servers = data.get("mcpServers")
    if not isinstance(mcp_servers, dict):
        raise McpParseError(
            f"'mcpServers' key is missing or not a dict in {mcp_json_path}"
        )

    out: list[ParsedMcpServer] = []
    for slug, cfg in mcp_servers.items():
        if not isinstance(cfg, dict):
            continue
        url = cfg.get("url")
        if not url or not isinstance(url, str):
            continue
        transport = cfg.get("type", "http")
        if not isinstance(transport, str):
            transport = "http"

        name_raw = cfg.get("name")
        name = name_raw if isinstance(name_raw, str) and name_raw else slug

        description_raw = cfg.get("description")
        description = description_raw if isinstance(description_raw, str) else None

        tool_name_map = build_tool_name_map(slug)

        out.append(ParsedMcpServer(
            slug=slug,
            name=name,
            url=url,
            transport=transport,
            description=description,
            tool_name_map=tool_name_map,
            raw_manifest=dict(cfg),
            source_path=str(mcp_json_path),
        ))

    return out


def discover_mcp_json_files(upstream_plugins_root: Path) -> list[Path]:
    """Return paths to every ``.mcp.json`` under vertical-plugins/."""
    verticals_dir = upstream_plugins_root / "vertical-plugins"
    if not verticals_dir.is_dir():
        raise McpParseError(
            f"expected vertical-plugins directory under {upstream_plugins_root}"
        )
    return sorted(verticals_dir.glob("*/.mcp.json"))


def collect_all_mcp_servers(upstream_plugins_root: Path) -> list[ParsedMcpServer]:
    """Merge all MCP definitions across all .mcp.json files.

    Later files' entries override earlier ones with the same slug.
    The canonical source (financial-analysis) is loaded first, so
    subsequent files can override — but in this upstream those are empty.
    """
    seen: dict[str, ParsedMcpServer] = {}
    for json_path in discover_mcp_json_files(upstream_plugins_root):
        for server in parse_mcp_json(json_path):
            seen[server.slug] = server
    # Sort for deterministic output
    return [seen[k] for k in sorted(seen)]