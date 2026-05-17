"""Snapshot + diff (Phase 3, PRD §10.2)."""

from __future__ import annotations

from pathlib import Path

from expression import (
    Model,
    diff_cells,
    format_diff,
    glob,
    periods,
    read_snapshot,
    row,
    serialize_cells,
    write_snapshot,
)


class _Tiny(Model):
    time = periods(2024, 2026)
    seed = glob(100)
    growth = glob(0.10)

    @row
    def x(self, t):
        if t == self.time.first:
            return self.seed
        return self.x(t - 1) * (1 + self.growth)


def test_serialize_and_roundtrip(tmp_path: Path) -> None:
    m = _Tiny()
    m.solve()
    cells = serialize_cells(m)
    assert cells["x[2024]"] == 100
    assert "x[2025]" in cells
    path = write_snapshot(tmp_path, cells)
    assert path.exists()
    loaded = read_snapshot(tmp_path)
    assert loaded == cells


def test_diff_changed_added_removed() -> None:
    a = {"x[2024]": 100, "x[2025]": 110}
    b = {"x[2024]": 100, "x[2025]": 120, "x[2026]": 130}
    # current = b, snapshot = a → x[2025] changed, x[2026] added
    report = diff_cells(b, a)
    assert len(report.changed) == 1
    assert report.changed[0].key == "x[2025]"
    assert report.changed[0].before == 110
    assert report.changed[0].after == 120
    assert len(report.added) == 1
    assert report.added[0].key == "x[2026]"
    assert not report.removed
    text = format_diff(report)
    assert "x[2025]" in text
    assert "x[2026]" in text


def test_diff_empty_when_identical() -> None:
    cells = {"x[2024]": 1.0}
    report = diff_cells(cells, cells)
    assert report.empty
    assert format_diff(report) == "(no diff vs snapshot)"


def test_read_snapshot_missing_returns_none(tmp_path: Path) -> None:
    assert read_snapshot(tmp_path) is None
