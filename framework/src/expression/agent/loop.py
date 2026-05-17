"""The interactive agent loop.

Holds the conversation state, dispatches tool calls back into the
workspace, and emits trace events. The harness is injected — swap
``anthropic-api`` for ``claude-code`` (or your own) without touching
this file.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from ..trace import Tracer
from .context import gather
from .harness import Harness, Message, ToolCall, ToolSpec
from .skills import builtin_skills_dir, load_skills, skills_to_system_text
from .tools import ToolEnv, execute, tool_specs

_DEFAULT_SYSTEM_PREFIX = (
    "You are the agent half of `model` — a CLI for spreadsheet-as-DAG "
    "Python models (PRD: SPECIFICATION.md). The user is iterating on a "
    "model in their workspace. Follow these rules:\n\n"
    "- Make ONE small change at a time, then run `expression run` and check the "
    "  diff before proposing the next step (small-step-iteration skill).\n"
    "- Never bake hardcoded one-off values into formulas; record them as "
    "  overrides via `expression overrides add` (override-discipline skill).\n"
    "- After any code change, run `expression test` and `expression run`. Don't "
    "  declare success without a green run.\n"
    "- When asking the user a question, ask ONE thing at a time.\n"
    "- Reference cells with backticks, e.g. `budget[2024]`, so the doc-sync "
    "  picks them up.\n"
)


@dataclass
class LoopConfig:
    workspace: Path
    harness: Harness
    skills_dir: Path = field(default_factory=builtin_skills_dir)
    auto_confirm_tools: bool = False
    max_turns: int = 50
    out: IO[str] | None = None  # None ⇒ stdout (lazy-bound at runtime)
    in_: Callable[[str], str] | None = None  # None ⇒ builtins.input


@dataclass
class LoopState:
    messages: list[Message] = field(default_factory=list)
    turns: int = 0


def build_system_prompt(workspace: Path, skills_dir: Path) -> str:
    """Compose: agent rules + skills + workspace snapshot."""
    skills = load_skills(skills_dir)
    skills_text = skills_to_system_text(skills)
    ctx = gather(workspace)
    return "\n".join(
        part for part in (_DEFAULT_SYSTEM_PREFIX, skills_text, ctx.to_prompt()) if part
    )


def run_loop(config: LoopConfig, opening_user_message: str | None = None) -> LoopState:
    """Drive the loop until the user types ``exit`` or max turns reached."""
    import sys as _sys

    out = config.out or _sys.stdout
    read_input: Callable[[str], str] = config.in_ if config.in_ is not None else input
    state = LoopState()
    system = build_system_prompt(config.workspace, config.skills_dir)
    tools = tool_specs() if config.harness.supports_tools() else []
    env = ToolEnv(workspace=config.workspace.resolve())

    with Tracer(config.workspace) as tracer:
        tracer.event(
            "loop.start",
            workspace=str(config.workspace),
            harness=getattr(config.harness, "name", type(config.harness).__name__),
            tools=[t.name for t in tools],
        )

        first = opening_user_message
        while state.turns < config.max_turns:
            if first is not None:
                user_text = first
                first = None
            else:
                try:
                    user_text = read_input("» ")
                except (EOFError, KeyboardInterrupt):
                    out.write("\n(exiting)\n")
                    break
            if not user_text.strip():
                continue
            if user_text.strip().lower() in ("exit", "quit", ":q"):
                out.write("(bye)\n")
                break

            state.messages.append(Message(role="user", content=user_text))
            tracer.event("user.message", text=user_text)

            # Inner agent step: keep calling the harness until it stops
            # asking for tool calls. The harness itself doesn't loop —
            # we do, so trace and confirmation flow through one place.
            while True:
                response = config.harness.chat(state.messages, system, tools)
                tracer.event(
                    "harness.response",
                    text=response.text,
                    tool_calls=[
                        {"id": tc.id, "name": tc.name, "args": tc.args}
                        for tc in response.tool_calls
                    ],
                    stop_reason=response.stop_reason,
                    usage=response.usage,
                )

                # Record the assistant turn (with both text and tool_use blocks
                # if any) so the next turn includes the matching tool_result.
                assistant_blocks: list[dict[str, Any]] = []
                if response.text:
                    assistant_blocks.append({"type": "text", "text": response.text})
                for tc in response.tool_calls:
                    assistant_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.args,
                        }
                    )
                state.messages.append(
                    Message(role="assistant", content=assistant_blocks or response.text)
                )

                if response.text:
                    out.write(response.text + "\n")
                    out.flush()

                if not response.tool_calls:
                    break  # turn ends, back to user prompt

                # Dispatch each tool call, gating writes/runs on confirmation.
                tool_results: list[dict[str, Any]] = []
                for tc in response.tool_calls:
                    if not _confirm_tool_call(tc, config.auto_confirm_tools, out, read_input):
                        result_text = "<user declined this tool call>"
                    else:
                        try:
                            result_text = execute(tc.name, tc.args, env)
                        except Exception as exc:
                            result_text = f"<tool error: {type(exc).__name__}: {exc}>"
                    tracer.event(
                        "tool.result",
                        id=tc.id,
                        name=tc.name,
                        args=tc.args,
                        result_preview=result_text[:500],
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result_text,
                        }
                    )
                state.messages.append(Message(role="user", content=tool_results))

            state.turns += 1

        tracer.event("loop.end", turns=state.turns)
    return state


def _confirm_tool_call(
    tc: ToolCall, auto: bool, out: IO[str], read_input: Callable[[str], str]
) -> bool:
    """Prompt the user before any write/run tool call. Reads are auto-OK."""
    if tc.name == "read_file" or auto:
        return True
    summary = json.dumps(tc.args, default=str)
    if len(summary) > 200:
        summary = summary[:200] + "…"
    out.write(f"\n[tool] {tc.name}({summary})\n")
    out.write("Proceed? [y/N] ")
    out.flush()
    try:
        answer = read_input("").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def quick_specs_for_test() -> list[ToolSpec]:
    """Helper for tests that mock harnesses — exposes the canonical specs."""
    return tool_specs()
