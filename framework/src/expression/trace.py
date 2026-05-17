"""Structured JSON-lines trace logging to ``.model/trace/`` (PRD §11).

The agent loop emits one line per event so downstream analyzers (and the
agent itself, on the next run) can replay what happened. Format is JSON
Lines: each line is a self-contained ``{"ts": ..., "kind": ..., ...}``
record.

This module is intentionally tiny — no dependency on ``structlog``. If we
ever need richer features (correlation IDs, redaction), swap the file
backend without changing callers.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType
from typing import Any


def trace_dir(model_dir: Path) -> Path:
    return model_dir / ".model" / "trace"


class Tracer(AbstractContextManager["Tracer"]):
    """Append-only JSONL writer rooted at ``.model/trace/<session>.jsonl``.

    A session is one agent run. Sessions are named by start time so that
    consecutive runs don't clobber each other.
    """

    def __init__(self, model_dir: Path, session: str | None = None) -> None:
        self.dir = trace_dir(model_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.session = session or time.strftime("%Y%m%dT%H%M%S")
        self.path = self.dir / f"{self.session}.jsonl"
        self._fh: Any = None

    def __enter__(self) -> Tracer:
        self._fh = self.path.open("a", encoding="utf-8")
        self.event("session.start", pid=os.getpid())
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            self.event("session.error", error=str(exc), error_type=type(exc).__name__)
        self.event("session.end")
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def event(self, kind: str, **fields: Any) -> None:
        record: dict[str, Any] = {"ts": time.time(), "kind": kind, **fields}
        line = json.dumps(record, default=str)
        if self._fh is None:
            # Allow event() outside a `with` block — useful in CLI commands.
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            self._fh.write(line + "\n")
            self._fh.flush()
