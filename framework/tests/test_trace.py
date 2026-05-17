"""Trace logging (Phase 3, PRD §11)."""

from __future__ import annotations

import json
from pathlib import Path

from expression import Tracer


def test_tracer_writes_jsonlines(tmp_path: Path) -> None:
    with Tracer(tmp_path, session="test") as t:
        t.event("hello", x=1)
        t.event("done", note="ok")
    lines = (tmp_path / ".model" / "trace" / "test.jsonl").read_text().strip().splitlines()
    records = [json.loads(line) for line in lines]
    kinds = [r["kind"] for r in records]
    assert "session.start" in kinds
    assert "hello" in kinds
    assert "done" in kinds
    assert "session.end" in kinds
    hello = next(r for r in records if r["kind"] == "hello")
    assert hello["x"] == 1


def test_tracer_event_outside_context(tmp_path: Path) -> None:
    t = Tracer(tmp_path, session="oneshot")
    t.event("standalone", note="nocontext")
    text = (tmp_path / ".model" / "trace" / "oneshot.jsonl").read_text()
    assert "standalone" in text
