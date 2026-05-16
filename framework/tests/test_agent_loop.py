"""Agent loop with a mock harness (Phase 3)."""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sweet.agent.harness import (
    HarnessResponse,
    Message,
    ToolCall,
    ToolSpec,
    get_harness,
    list_harnesses,
    register_harness,
)
from sweet.agent.loop import LoopConfig, run_loop


@dataclass
class _ScriptedHarness:
    """Replays a list of pre-baked HarnessResponses, ignoring inputs."""

    name: str = "scripted"
    script: list[HarnessResponse] = field(default_factory=list)
    seen: list[tuple[list[Message], str, list[ToolSpec]]] = field(default_factory=list)
    _idx: int = 0

    def supports_tools(self) -> bool:
        return True

    def chat(
        self, messages: list[Message], system: str, tools: list[ToolSpec]
    ) -> HarnessResponse:
        self.seen.append((list(messages), system, list(tools)))
        out = self.script[self._idx]
        self._idx = min(self._idx + 1, len(self.script) - 1)
        return out


def test_builtin_harnesses_registered() -> None:
    names = list_harnesses()
    assert "anthropic-api" in names
    assert "claude-code" in names


def test_register_unknown_raises() -> None:
    try:
        get_harness("nope")
    except KeyError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def _scripted_input(*lines: str) -> Callable[[str], str]:
    """Build an input-callable that returns each line in turn, then EOFs."""
    it = iter(lines)

    def _read(_prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError from exc

    return _read


def test_loop_dispatches_read_file_tool(tmp_path: Path) -> None:
    """End-to-end: scripted harness asks for a file, loop reads it back."""
    (tmp_path / "sweet.py").write_text("# fake model\n")
    harness = _ScriptedHarness(
        script=[
            HarnessResponse(
                tool_calls=[ToolCall(id="t1", name="read_file", args={"path": "sweet.py"})],
                stop_reason="tool_use",
            ),
            HarnessResponse(text="ok, I read it.", stop_reason="end_turn"),
        ]
    )
    out = io.StringIO()
    state = run_loop(
        LoopConfig(
            workspace=tmp_path,
            harness=harness,  # type: ignore[arg-type]
            auto_confirm_tools=True,
            max_turns=2,
            out=out,
            in_=_scripted_input("hi", "exit"),
        ),
    )
    assert state.turns == 1
    output = out.getvalue()
    assert "ok, I read it." in output
    # The second harness call must have seen the tool result fed back in.
    assert len(harness.seen) == 2
    # The most recent user message in the second call should be the tool result.
    second_call_messages = harness.seen[1][0]
    last = second_call_messages[-1]
    assert last.role == "user"
    assert isinstance(last.content, list)
    assert last.content[0]["type"] == "tool_result"
    assert "fake model" in last.content[0]["content"]


def test_loop_skips_tools_when_harness_doesnt_support_them(tmp_path: Path) -> None:
    @dataclass
    class _NoTools:
        name: str = "notools"
        seen_tools: list[list[ToolSpec]] = field(default_factory=list)

        def supports_tools(self) -> bool:
            return False

        def chat(
            self, messages: list[Message], system: str, tools: list[ToolSpec]
        ) -> HarnessResponse:
            self.seen_tools.append(list(tools))
            return HarnessResponse(text="reply", stop_reason="end_turn")

    h = _NoTools()
    out = io.StringIO()
    run_loop(
        LoopConfig(
            workspace=tmp_path,
            harness=h,  # type: ignore[arg-type]
            max_turns=1,
            out=out,
            in_=_scripted_input("hi", "exit"),
        ),
    )
    assert h.seen_tools == [[]]


def test_run_model_tool_runs_in_workspace(tmp_path: Path) -> None:
    """``run_model`` tool dispatches via ``python -m model``."""
    from sweet.agent.tools import ToolEnv, execute

    # Create a minimal valid workspace
    (tmp_path / "sweet.py").write_text(
        "from sweet import Model, periods, glob, row\n\n"
        "class M(Model):\n"
        "    time = periods(2024, 2025)\n"
        "    seed = glob(10)\n"
        "    @row\n"
        "    def x(self, t):\n"
        "        return self.seed if t == self.time.first else self.x(t-1) + 1\n"
    )
    env = ToolEnv(workspace=tmp_path.resolve())
    result = execute("run_model", {"subcommand": "run"}, env)
    assert "[exit 0]" in result
    assert "Solved" in result


def test_register_overrides_existing() -> None:
    register_harness("scripted", lambda: _ScriptedHarness())  # type: ignore[arg-type]
    h = get_harness("scripted")
    assert h.name == "scripted"
