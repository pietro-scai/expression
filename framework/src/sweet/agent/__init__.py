"""``model.agent`` — interactive agent loop and pluggable LLM harnesses.

Phase 3 ships two harnesses out of the box:

- ``anthropic-api`` (default) — uses the Anthropic API directly via the
  ``anthropic`` SDK. See :mod:`model.agent.harnesses.anthropic_api` for
  configuration (``ANTHROPIC_API_KEY``).
- ``claude-code`` — shells out to a locally-installed ``claude`` CLI.

To add a new harness, implement :class:`~model.agent.harness.Harness` and
register it via :func:`~model.agent.harness.register_harness`. The
``harness-adapter`` skill (see ``model/skills/harness-adapter``) walks
through the contract and gives a working template.
"""

from __future__ import annotations

from .harness import Harness, HarnessResponse, ToolCall, get_harness, register_harness
from .skills import Skill, load_skills, skills_to_system_text

__all__ = [
    "Harness",
    "HarnessResponse",
    "Skill",
    "ToolCall",
    "get_harness",
    "load_skills",
    "register_harness",
    "skills_to_system_text",
]


# Eagerly register the built-in harnesses so callers don't need to import
# the submodules. Each module calls register_harness() at import time.
from .harnesses import (  # pyright: ignore[reportUnusedImport]
    anthropic_api,
    claude_code,
)

_BUILTIN_HARNESS_MODULES = (anthropic_api, claude_code)
