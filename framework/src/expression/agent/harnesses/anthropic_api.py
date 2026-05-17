"""Anthropic API harness — drives the loop via the ``anthropic`` SDK.

API key
-------

The SDK reads ``ANTHROPIC_API_KEY`` from the environment by default. Get
a key from https://console.anthropic.com/settings/keys, then either::

    export ANTHROPIC_API_KEY=sk-ant-...

or pass it inline for one invocation::

    ANTHROPIC_API_KEY=sk-ant-... expression agent

If the variable is missing, ``expression agent`` exits with a clear error
before any network call is attempted.

Model
-----

Defaults to ``claude-sonnet-4-6`` (fast + capable, good fit for an agent
loop). Override with ``--model`` on the CLI or ``MODEL_AGENT_MODEL`` in
the environment.

Caching
-------

The system prompt (skills + workspace context) is marked
``cache_control: ephemeral`` so re-runs within the 5-minute TTL hit the
prompt cache instead of re-billing the whole prefix. Worth ~90% off the
input cost for the long skill block.
"""

from __future__ import annotations

import os
from typing import Any

from ..harness import (
    Harness,
    HarnessResponse,
    Message,
    ToolCall,
    ToolSpec,
    register_harness,
)

DEFAULT_MODEL = os.environ.get("MODEL_AGENT_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = 4096


class AnthropicAPIHarness:
    """:class:`~model.agent.harness.Harness` backed by the Anthropic SDK."""

    name = "anthropic-api"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "The 'anthropic' SDK is not installed. Install it with:\n"
                "    pip install anthropic\n"
                "or, if you use uv:\n"
                "    uv add anthropic\n"
                "Then set ANTHROPIC_API_KEY (https://console.anthropic.com/settings/keys)."
            ) from exc
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set.\n"
                "  1) Get a key: https://console.anthropic.com/settings/keys\n"
                "  2) Export it: export ANTHROPIC_API_KEY=sk-ant-...\n"
                "  3) Re-run: model agent"
            )
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model
        self._max_tokens = max_tokens

    def supports_tools(self) -> bool:
        return True

    def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolSpec],
    ) -> HarnessResponse:
        api_messages = [_to_api_message(m) for m in messages]
        api_tools = [_tool_spec_to_api(t) for t in tools]

        # Cache the (long) system prompt so re-runs within the 5-minute
        # cache TTL skip re-billing the skills + workspace prefix.
        system_blocks = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_blocks,
            messages=api_messages,
            tools=api_tools,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        args=dict(block.input or {}),
                    )
                )

        usage = {}
        if response.usage is not None:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_input_tokens": getattr(
                    response.usage, "cache_read_input_tokens", 0
                ),
                "cache_creation_input_tokens": getattr(
                    response.usage, "cache_creation_input_tokens", 0
                ),
            }

        return HarnessResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
            usage=usage,
        )


def _to_api_message(m: Message) -> dict[str, Any]:
    if isinstance(m.content, str):
        return {"role": m.role, "content": m.content}
    return {"role": m.role, "content": m.content}


def _tool_spec_to_api(t: ToolSpec) -> dict[str, Any]:
    return {
        "name": t.name,
        "description": t.description,
        "input_schema": t.input_schema,
    }


register_harness("anthropic-api", AnthropicAPIHarness)


# Quiet pyright: register_harness wants Harness, AnthropicAPIHarness fits.
_typed_check: type[Harness] = AnthropicAPIHarness  # type: ignore[type-abstract]
