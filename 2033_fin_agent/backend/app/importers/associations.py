"""Compute association tables (vertical_skills, vertical_mcps, agent_mcps).

Pure: takes parsed records and returns association tuples. Does not write
to Supabase. Used by the dry-run CLI to surface candidate associations and
flag any agent tool references that don't resolve to a known MCP slug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .agent_parser import ParsedAgent
from .mcp_parser import ParsedMcpServer, build_tool_name_map
from .skill_parser import ParsedSkill
from .vertical_parser import ParsedVertical


_AGENT_TOOL_MCP_RE = re.compile(r"mcp__([A-Za-z0-9_\-]+)__")


@dataclass(frozen=True)
class AgentMcpCandidate:
    agent_slug: str
    referenced_alias: str
    resolved_mcp_slug: str | None
    resolution: str


def derive_vertical_skill_associations(
    skills: list[ParsedSkill],
) -> list[tuple[str, str]]:
    """Each skill is owned by exactly one vertical (derived from path)."""
    pairs: list[tuple[str, str]] = []
    for skill in skills:
        if skill.vertical_slug:
            pairs.append((skill.vertical_slug, skill.slug))
    return pairs


def derive_vertical_mcp_associations(
    mcps: list[ParsedMcpServer],
) -> list[tuple[str, str]]:
    """Each MCP is associated with the vertical whose .mcp.json declared it."""
    pairs: list[tuple[str, str]] = []
    for mcp in mcps:
        path_parts = mcp.source_path.split("/")
        if "vertical-plugins" in path_parts:
            idx = path_parts.index("vertical-plugins")
            if idx + 1 < len(path_parts):
                pairs.append((path_parts[idx + 1], mcp.slug))
    return pairs


def derive_agent_mcp_candidates(
    agents: list[ParsedAgent],
    mcps: list[ParsedMcpServer],
) -> list[AgentMcpCandidate]:
    """Cross-reference agent ``tools:`` frontmatter against MCP slugs.

    For each ``mcp__<alias>__`` token in an agent's ``tools`` frontmatter:
    - ``matched``: alias exactly equals a known MCP slug.
    - ``aliased``: alias is a documented alias of a known MCP slug.
    - ``unmatched``: alias does not resolve (typically a placeholder MCP like
      ``internal-gl`` that firms are expected to bring themselves).
    """
    mcp_slugs = {m.slug for m in mcps}
    alias_to_slug: dict[str, str] = {}
    for mcp in mcps:
        for alias, canonical in build_tool_name_map(mcp.slug).items():
            alias_to_slug[alias] = canonical

    out: list[AgentMcpCandidate] = []
    for agent in agents:
        tools_value = agent.raw_frontmatter.get("tools")
        if not isinstance(tools_value, str):
            continue
        seen_in_agent: set[str] = set()
        for match in _AGENT_TOOL_MCP_RE.finditer(tools_value):
            alias = match.group(1)
            if alias in seen_in_agent:
                continue
            seen_in_agent.add(alias)
            if alias in mcp_slugs:
                resolution = "matched"
                resolved = alias
            elif alias in alias_to_slug:
                resolution = "aliased"
                resolved = alias_to_slug[alias]
            else:
                resolution = "unmatched"
                resolved = None
            out.append(AgentMcpCandidate(
                agent_slug=agent.slug,
                referenced_alias=alias,
                resolved_mcp_slug=resolved,
                resolution=resolution,
            ))
    return out
