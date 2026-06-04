"""Parse upstream financial-services agent markdown into structured fields.

This module is pure: it takes file paths and returns dataclasses. It has no
Supabase, FastAPI, or filesystem-write side effects. The parser exists as
its own module so it can be unit-tested without any external dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class AgentParseError(ValueError):
    """Raised when an agent markdown file cannot be parsed."""


@dataclass(frozen=True)
class ParsedAgent:
    slug: str
    name: str
    description: str | None
    system_prompt: str
    workflow: str | None
    guardrails: str | None
    outputs: str | None
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)
    plugin_metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


_FRONTMATTER_RE = re.compile(
    r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)


_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "outputs": ("what you produce", "what it produces", "outputs"),
    "workflow": ("workflow",),
    "guardrails": ("guardrails", "guard rails"),
}


def parse_agent_file(agent_md_path: Path, plugin_json_path: Path) -> ParsedAgent:
    """Parse one agent markdown + its sibling plugin.json into a ParsedAgent."""
    if not agent_md_path.is_file():
        raise AgentParseError(f"agent markdown not found: {agent_md_path}")
    if not plugin_json_path.is_file():
        raise AgentParseError(f"plugin.json not found: {plugin_json_path}")

    raw = agent_md_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise AgentParseError(
            f"agent markdown missing YAML frontmatter: {agent_md_path}"
        )

    try:
        frontmatter = yaml.safe_load(match.group("frontmatter")) or {}
    except yaml.YAMLError as exc:
        raise AgentParseError(
            f"invalid YAML frontmatter in {agent_md_path}: {exc}"
        ) from exc
    if not isinstance(frontmatter, dict):
        raise AgentParseError(
            f"frontmatter is not a mapping in {agent_md_path}: got {type(frontmatter).__name__}"
        )

    slug = frontmatter.get("name")
    if not slug or not isinstance(slug, str):
        raise AgentParseError(
            f"frontmatter 'name' is required and must be a string in {agent_md_path}"
        )

    try:
        plugin_metadata = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentParseError(
            f"invalid JSON in {plugin_json_path}: {exc}"
        ) from exc
    if not isinstance(plugin_metadata, dict):
        raise AgentParseError(
            f"plugin.json is not a JSON object in {plugin_json_path}"
        )

    body = match.group("body").strip()
    sections = _split_h2_sections(body)

    description = frontmatter.get("description")
    if description is not None and not isinstance(description, str):
        raise AgentParseError(
            f"frontmatter 'description' must be a string in {agent_md_path}"
        )

    human_name = (
        plugin_metadata.get("name") if isinstance(plugin_metadata.get("name"), str) else None
    ) or slug

    return ParsedAgent(
        slug=slug,
        name=human_name,
        description=description,
        system_prompt=body,
        workflow=_pick_section(sections, _SECTION_ALIASES["workflow"]),
        guardrails=_pick_section(sections, _SECTION_ALIASES["guardrails"]),
        outputs=_pick_section(sections, _SECTION_ALIASES["outputs"]),
        raw_frontmatter=dict(frontmatter),
        plugin_metadata=plugin_metadata,
        source_path=str(agent_md_path),
    )


def discover_agent_files(upstream_plugins_root: Path) -> list[tuple[Path, Path]]:
    """Return (agent_md, plugin_json) pairs for every agent-plugins/<slug> entry.

    Only files that exist are returned; missing pairs are surfaced as parse
    errors when the caller actually invokes ``parse_agent_file``.
    """
    agents_dir = upstream_plugins_root / "agent-plugins"
    if not agents_dir.is_dir():
        raise AgentParseError(
            f"expected agent-plugins directory under {upstream_plugins_root}, "
            f"got {agents_dir}"
        )

    pairs: list[tuple[Path, Path]] = []
    for plugin_dir in sorted(p for p in agents_dir.iterdir() if p.is_dir()):
        for md_path in sorted(plugin_dir.glob("agents/*.md")):
            plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
            pairs.append((md_path, plugin_json))
    return pairs


def _split_h2_sections(body: str) -> dict[str, str]:
    """Split a markdown body into a {lowercased-heading: section-body} map."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in body.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip().lower()
            current_lines = []
        else:
            current_lines.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def _pick_section(sections: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = sections.get(alias)
        if value:
            return value
    return None
