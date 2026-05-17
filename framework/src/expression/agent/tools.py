"""Tools the harness can call.

Three tools are enough to let an agent iterate productively on a model:

- ``read_file`` — read any file in the workspace
- ``write_file`` — overwrite (or create) a file in the workspace
- ``run_model`` — invoke ``model <subcommand>`` and capture stdout/stderr

We deliberately *don't* expose unrestricted ``bash`` — the iteration
loop in PRD §8.3 is ``edit → run → diff → test → commit``, which only
needs ``model``. Adding more tools later is a one-function change.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .harness import ToolSpec

_ALLOWED_MODEL_SUBCOMMANDS = {
    "run",
    "show",
    "print",
    "diff",
    "explain",
    "test",
    "export",
    "import",
    "doc",
    "snapshot",
    "overrides",
    "init",
}


@dataclass
class ToolEnv:
    """Resolved workspace; tools refuse paths outside this root."""

    workspace: Path

    def resolve(self, rel: str) -> Path:
        candidate = (self.workspace / rel).resolve()
        # Reject path traversal: the resolved path must stay under workspace.
        try:
            candidate.relative_to(self.workspace.resolve())
        except ValueError as exc:
            raise PermissionError(
                f"Refusing to touch path outside workspace: {rel}"
            ) from exc
        return candidate


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="read_file",
            description=(
                "Read a UTF-8 text file relative to the model workspace. "
                "Returns the file contents."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the workspace root.",
                    }
                },
                "required": ["path"],
            },
        ),
        ToolSpec(
            name="write_file",
            description=(
                "Create or overwrite a UTF-8 text file inside the workspace. "
                "Use sparingly: every write is recorded in the trace."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        ),
        ToolSpec(
            name="run_model",
            description=(
                "Run a `model` CLI subcommand inside the workspace and return "
                "stdout + stderr + exit code. Allowed subcommands: "
                + ", ".join(sorted(_ALLOWED_MODEL_SUBCOMMANDS))
                + "."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "subcommand": {
                        "type": "string",
                        "description": (
                            "First word of the `model` command, e.g. 'run', "
                            "'show', 'diff'."
                        ),
                    },
                    "args": {
                        "type": "string",
                        "description": (
                            "Additional shell-quoted args passed verbatim to "
                            "`model <subcommand>`. Optional."
                        ),
                    },
                },
                "required": ["subcommand"],
            },
        ),
    ]


def execute(name: str, args: dict[str, Any], env: ToolEnv) -> str:
    """Dispatch a tool call. Returns the result as a string."""
    if name == "read_file":
        return _read_file(args["path"], env)
    if name == "write_file":
        return _write_file(args["path"], args["content"], env)
    if name == "run_model":
        return _run_model(args["subcommand"], args.get("args", ""), env)
    raise ValueError(f"Unknown tool: {name!r}")


def _read_file(path: str, env: ToolEnv) -> str:
    full = env.resolve(path)
    if not full.exists():
        return f"<error: file not found: {path}>"
    if not full.is_file():
        return f"<error: not a regular file: {path}>"
    try:
        return full.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"<error: not UTF-8 text: {path}>"


def _write_file(path: str, content: str, env: ToolEnv) -> str:
    full = env.resolve(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"<wrote {len(content)} bytes to {path}>"


def _resolve_model_cli() -> list[str]:
    """Find the ``model`` entry-point. Avoid ``python -m model`` because it
    collides with the user's ``expression.py`` when cwd is the workspace."""
    for cand in ("expression",):
        found = shutil.which(cand)
        if found:
            return [found]
    # Fallback: invoke via the package's __main__ but with a cwd-stripped
    # PYTHONPATH so the user's expression.py doesn't shadow the installed package.
    return [sys.executable, "-m", "expression"]


def _run_model(subcommand: str, extra: str, env: ToolEnv) -> str:
    if subcommand not in _ALLOWED_MODEL_SUBCOMMANDS:
        return (
            f"<error: subcommand {subcommand!r} not allowed. "
            f"Allowed: {sorted(_ALLOWED_MODEL_SUBCOMMANDS)}>"
        )
    extra_args = shlex.split(extra) if extra else []
    cmd = [*_resolve_model_cli(), subcommand, *extra_args]
    # Strip cwd from PYTHONPATH so ``import expression`` resolves to the installed
    # package, not the user's ``workspace/expression.py``.
    import os as _os
    env_vars = _os.environ.copy()
    env_vars["PYTHONPATH"] = _os.pathsep.join(
        p for p in env_vars.get("PYTHONPATH", "").split(_os.pathsep) if p and p != str(env.workspace)
    )
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(env.workspace),
        check=False,
        env=env_vars,
    )
    return (
        f"$ model {subcommand} {' '.join(extra_args)}\n"
        f"[exit {proc.returncode}]\n"
        f"---STDOUT---\n{proc.stdout}\n"
        f"---STDERR---\n{proc.stderr}"
    )
