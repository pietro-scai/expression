"""Skill loader (Anthropic ``SKILL.md`` convention).

A skill is a directory containing ``SKILL.md`` with YAML frontmatter::

    ---
    name: bottom-up-modeling
    description: When triggered, walks the user from leaf inputs upwards.
    ---
    # Body of the skill (markdown)

The agent loop concatenates the bodies of all loaded skills into the
system prompt. Skills are static at runtime — to add or change one, edit
the markdown file. No code change required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path


_FRONTMATTER = re.compile(
    r"^---\s*\n(.*?\n)---\s*\n(.*)$",
    re.DOTALL,
)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a tiny YAML-ish frontmatter block. Only ``key: value`` lines."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    raw, body = match.group(1), match.group(2)
    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, body


def load_skill(skill_md: Path) -> Skill:
    """Read a single ``SKILL.md`` and return a :class:`Skill`."""
    text = skill_md.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    name = fm.get("name") or skill_md.parent.name
    description = fm.get("description", "")
    return Skill(name=name, description=description, body=body.strip(), path=skill_md)


def load_skills(skills_dir: Path) -> list[Skill]:
    """Load every ``*/SKILL.md`` under ``skills_dir`` (sorted by name)."""
    if not skills_dir.exists():
        return []
    skills: list[Skill] = []
    for child in sorted(skills_dir.iterdir()):
        sm = child / "SKILL.md"
        if sm.exists():
            skills.append(load_skill(sm))
    return skills


def skills_to_system_text(skills: list[Skill]) -> str:
    """Concatenate skill bodies into a single system-prompt section."""
    if not skills:
        return ""
    parts = ["# Skills loaded for this session", ""]
    for s in skills:
        parts.append(f"## {s.name}")
        if s.description:
            parts.append(f"_{s.description}_")
        parts.append("")
        parts.append(s.body)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def builtin_skills_dir() -> Path:
    """Path to the skills shipped with this package."""
    return Path(__file__).resolve().parent.parent / "skills"
