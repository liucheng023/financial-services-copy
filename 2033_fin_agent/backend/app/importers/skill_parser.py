"""Parse upstream SKILL.md files into structured records.

Pure: no Supabase, no I/O beyond reading the given file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class SkillParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSkill:
    slug: str
    name: str
    description: str | None
    content: str
    vertical_slug: str | None
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


_FRONTMATTER_RE = re.compile(
    r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)


def parse_skill_file(skill_md_path: Path, vertical_slug: str | None) -> ParsedSkill:
    if not skill_md_path.is_file():
        raise SkillParseError(f"SKILL.md not found: {skill_md_path}")

    raw = skill_md_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise SkillParseError(f"SKILL.md missing YAML frontmatter: {skill_md_path}")

    try:
        frontmatter = yaml.safe_load(match.group("frontmatter")) or {}
    except yaml.YAMLError as exc:
        raise SkillParseError(f"invalid YAML frontmatter in {skill_md_path}: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise SkillParseError(
            f"frontmatter is not a mapping in {skill_md_path}"
        )

    slug = frontmatter.get("name")
    if not slug or not isinstance(slug, str):
        raise SkillParseError(
            f"frontmatter 'name' is required and must be a string in {skill_md_path}"
        )

    content = match.group("body").strip()
    name_raw = frontmatter.get("name")
    name = name_raw if isinstance(name_raw, str) and name_raw else slug
    description_raw = frontmatter.get("description")
    description = description_raw if isinstance(description_raw, str) else None

    return ParsedSkill(
        slug=slug,
        name=name,
        description=description,
        content=content,
        vertical_slug=vertical_slug,
        raw_frontmatter=dict(frontmatter),
        source_path=str(skill_md_path),
    )


def discover_skill_files(
    upstream_plugins_root: Path,
) -> list[tuple[Path, str | None]]:
    verticals_dir = upstream_plugins_root / "vertical-plugins"
    if not verticals_dir.is_dir():
        raise SkillParseError(
            f"expected vertical-plugins directory under {upstream_plugins_root}"
        )

    out: list[tuple[Path, str | None]] = []
    for vertical_dir in sorted(p for p in verticals_dir.iterdir() if p.is_dir()):
        skills_dir = vertical_dir / "skills"
        v_slug = vertical_dir.name
        if skills_dir.is_dir():
            for skill_dir in sorted(skills_dir.iterdir()):
                md = skill_dir / "SKILL.md"
                if md.is_file():
                    out.append((md, v_slug))
    return out