"""Workspace context the agent loop hands to the harness.

Reads the small set of files an agent needs to be useful in a model
folder: ``sweet.py``, ``sweet.md``, ``overrides.toml``, last solve
result. Files that don't exist are skipped silently — a fresh ``model
init`` workspace is a perfectly valid starting point.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_FILES = ("sweet.py", "sweet.md", "overrides.toml", "outputs/result.json")


@dataclass(frozen=True)
class WorkspaceContext:
    workspace: Path
    files: dict[str, str]  # rel-path → contents

    def to_prompt(self) -> str:
        if not self.files:
            return f"# Workspace: {self.workspace} (empty)"
        parts = [f"# Workspace: {self.workspace}", ""]
        for rel, content in self.files.items():
            parts.append(f"## {rel}")
            parts.append("```")
            parts.append(content)
            parts.append("```")
            parts.append("")
        return "\n".join(parts)


def gather(workspace: Path, extra_files: list[str] | None = None) -> WorkspaceContext:
    files: dict[str, str] = {}
    for rel in (*_FILES, *(extra_files or [])):
        path = workspace / rel
        if path.exists() and path.is_file():
            try:
                files[rel] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Skip binaries silently — the agent doesn't need them inline.
                continue
    return WorkspaceContext(workspace=workspace.resolve(), files=files)
