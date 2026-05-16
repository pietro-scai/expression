"""Pluggable harness contract.

A *harness* is whatever drives the conversation: the Anthropic API
directly, the local Claude Code CLI, an OpenAI gateway, etc. Each harness
takes a list of messages plus a system prompt and returns either text or a
set of tool calls.

The contract is intentionally minimal so we can swap implementations
without changing the loop. If a harness can't do tool calls (e.g. an
external CLI driving its own tools), it returns plain text and the loop
treats the response as user-facing prose.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation requested by the model.

    ``id`` is the harness-assigned identifier; the loop uses it to match
    a tool *result* back to this call when it sends the next turn.
    """

    id: str
    name: str
    args: dict[str, Any]


@dataclass
class HarnessResponse:
    """Result of one harness turn.

    Either ``text`` is non-empty (assistant prose), or ``tool_calls`` is
    non-empty (the model wants to invoke tools), or both. ``stop_reason``
    is the harness-native stop reason ("end_turn", "tool_use", etc.).
    """

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    """JSON-schema description of a tool the harness can offer the model."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class Message:
    """One conversational turn.

    Roles: "user" or "assistant". ``content`` is either plain text, or a
    list of structured blocks (text / tool_use / tool_result) for harnesses
    that support tool use round-trips.
    """

    role: str
    content: Any  # str | list[dict[str, Any]]


class Harness(Protocol):
    """Minimal contract a harness must satisfy.

    Implementations live in :mod:`model.agent.harnesses` and register
    themselves via :func:`register_harness`. The loop only ever talks to
    this protocol — keep it small.
    """

    name: str

    def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolSpec],
    ) -> HarnessResponse:
        """One turn. Pure function from inputs to a response."""
        ...

    def supports_tools(self) -> bool:
        """Whether the harness can drive tool calls itself.

        ``False`` means the harness produces text only; the loop won't pass
        ``tools`` and will treat the response as user-facing prose. The
        ``claude-code`` harness returns ``False`` because the external CLI
        owns its own tool loop.
        """
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HarnessFactory = Callable[[], Harness]
_REGISTRY: dict[str, HarnessFactory] = {}


def register_harness(name: str, factory: HarnessFactory) -> None:
    """Register a harness factory under ``name``.

    Idempotent: re-registering the same name overwrites the previous
    factory (useful for testing with mock harnesses).
    """
    _REGISTRY[name] = factory


def get_harness(name: str) -> Harness:
    """Construct and return the harness registered under ``name``."""
    if name not in _REGISTRY:
        avail = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown harness: {name!r}. Available: {avail}")
    return _REGISTRY[name]()


def list_harnesses() -> list[str]:
    return sorted(_REGISTRY)
