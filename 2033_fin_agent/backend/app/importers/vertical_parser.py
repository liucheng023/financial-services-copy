"""Parse upstream vertical-plugins/<vertical>/.claude-plugin/plugin.json files.

Returns structured records suitable for the ``verticals`` table. Pure: no
Supabase, no I/O beyond reading the given file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class VerticalParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedVertical:
    slug: str
    name: str
    description: str | None
    raw_manifest: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


def parse_vertical_plugin(plugin_json_path: Path, vertical_slug: str) -> ParsedVertical:
    if not plugin_json_path.is_file():
        raise VerticalParseError(f"vertical plugin.json not found: {plugin_json_path}")

    try:
        manifest = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerticalParseError(
            f"invalid JSON in {plugin_json_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise VerticalParseError(
            f"plugin.json is not a JSON object in {plugin_json_path}"
        )

    name_raw = manifest.get("name")
    name = name_raw if isinstance(name_raw, str) and name_raw else vertical_slug
    description_raw = manifest.get("description")
    description = description_raw if isinstance(description_raw, str) else None

    return ParsedVertical(
        slug=vertical_slug,
        name=name,
        description=description,
        raw_manifest=manifest,
        source_path=str(plugin_json_path),
    )


def discover_vertical_plugins(upstream_plugins_root: Path) -> list[tuple[Path, str]]:
    verticals_dir = upstream_plugins_root / "vertical-plugins"
    if not verticals_dir.is_dir():
        raise VerticalParseError(
            f"expected vertical-plugins directory under {upstream_plugins_root}, "
            f"got {verticals_dir}"
        )

    out: list[tuple[Path, str]] = []
    for vertical_dir in sorted(p for p in verticals_dir.iterdir() if p.is_dir()):
        plugin_json = vertical_dir / ".claude-plugin" / "plugin.json"
        if plugin_json.is_file():
            out.append((plugin_json, vertical_dir.name))
    return out
