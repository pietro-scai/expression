"""Skill loader (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from expression.agent.skills import (
    builtin_skills_dir,
    load_skill,
    load_skills,
    skills_to_system_text,
)


def test_loads_builtin_skills() -> None:
    skills = load_skills(builtin_skills_dir())
    names = {s.name for s in skills}
    expected = {
        "bottom-up-modeling",
        "small-step-iteration",
        "parameter-elicitation",
        "circularity-resolution",
        "override-discipline",
        "excel-fidelity",
        "import-excel",
        "harness-adapter",
    }
    assert expected <= names


def test_skills_to_system_text() -> None:
    skills = load_skills(builtin_skills_dir())
    text = skills_to_system_text(skills)
    assert "small-step-iteration" in text
    assert "harness-adapter" in text


def test_load_skill_parses_frontmatter(tmp_path: Path) -> None:
    sd = tmp_path / "x"
    sd.mkdir()
    (sd / "SKILL.md").write_text(
        "---\nname: x\ndescription: test skill\n---\n\nbody here\n"
    )
    s = load_skill(sd / "SKILL.md")
    assert s.name == "x"
    assert s.description == "test skill"
    assert "body here" in s.body
