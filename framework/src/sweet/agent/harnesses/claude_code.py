"""Claude Code harness — shells out to a local ``claude`` CLI.

Use this when you'd rather drive the agent through Claude Code (which
manages its own tool loop, file edits, etc.) than the bare API. The
harness sends one user prompt at a time via ``claude --print`` and
returns whatever the CLI prints. Tool use is *not* exposed back to the
loop — Claude Code owns its own tools.

Setup
-----

1. Install the Claude Code CLI: https://docs.claude.com/en/docs/claude-code
2. Run ``claude /login`` once to authenticate.
3. Optionally set ``MODEL_AGENT_CLAUDE_CMD`` if your CLI binary isn't on
   ``PATH`` as ``claude``.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from ..harness import (
    Harness,
    HarnessResponse,
    Message,
    ToolSpec,
    register_harness,
)

CLAUDE_BIN = os.environ.get("MODEL_AGENT_CLAUDE_CMD", "claude")


class ClaudeCodeHarness:
    """Harness that shells out to the local ``claude`` CLI."""

    name = "claude-code"

    def __init__(self, claude_bin: str = CLAUDE_BIN) -> None:
        if shutil.which(claude_bin) is None:
            raise RuntimeError(
                f"'{claude_bin}' is not on PATH. Install Claude Code "
                "(https://docs.claude.com/en/docs/claude-code) or set "
                "MODEL_AGENT_CLAUDE_CMD to the binary path."
            )
        self._bin = claude_bin

    def supports_tools(self) -> bool:
        # Claude Code drives its own tools — don't pass tool specs through.
        return False

    def chat(
        self,
        messages: list[Message],
        system: str,
        tools: list[ToolSpec],
    ) -> HarnessResponse:
        # Build a single prompt by concatenating system + the latest user
        # message. We don't try to replay full history — Claude Code has
        # its own session memory; the loop manages turn-level context.
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        if not isinstance(last_user, str):
            last_user = _flatten(last_user)
        prompt = f"{system}\n\n---\n\n{last_user}".strip()
        proc = subprocess.run(
            [self._bin, "--print", "--append-system-prompt", system, prompt],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {proc.returncode}: {proc.stderr.strip()}"
            )
        return HarnessResponse(text=proc.stdout.strip(), stop_reason="end_turn")


def _flatten(content: object) -> str:
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                chunks.append(str(block.get("text", "")))
        return "\n".join(chunks)
    return str(content)


register_harness("claude-code", ClaudeCodeHarness)


_typed_check: type[Harness] = ClaudeCodeHarness  # type: ignore[type-abstract]
