"""Tests for overrides.toml + apply_overrides + the model overrides CLI."""

from __future__ import annotations

import math
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from sweet import Model, ModelError, glob, periods, row
from sweet.overrides import (
    Override,
    apply_overrides,
    read_overrides,
    write_overrides,
)


class _PnL(Model):
    time = periods(2024, 2026)
    revenue_growth = glob(0.10)
    cogs_pct = glob(0.40)

    @row
    def revenue(self, t):
        if t == self.time.first:
            return 1000
        return self.revenue(t - 1) * (1 + self.revenue_growth)

    @row
    def cogs(self, t):
        return self.revenue(t) * self.cogs_pct

    @row
    def gross_profit(self, t):
        return self.revenue(t) - self.cogs(t)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def test_row_override_propagates_downstream():
    """PRD example 12.3: revenue[2025] override changes downstream values."""
    m = _PnL()
    apply_overrides(m, [Override(target="revenue", period=2025, value=1500)])
    m.solve()
    rev = m.series("revenue")
    assert rev[0] == 1000
    assert rev[1] == 1500
    assert math.isclose(rev[2], 1650.0, rel_tol=1e-9)
    assert math.isclose(m.cell("cogs", 2025), 1500 * 0.40)
    assert math.isclose(m.cell("gross_profit", 2026), 1650.0 * 0.6, rel_tol=1e-9)


def test_glob_override_takes_effect():
    m = _PnL()
    apply_overrides(m, [Override(target="revenue_growth", value=0.20, kind="glob")])
    m.solve()
    rev = m.series("revenue")
    assert rev[0] == 1000
    assert math.isclose(rev[1], 1200.0)
    assert math.isclose(rev[2], 1440.0)


def test_unknown_target_raises():
    m = _PnL()
    with pytest.raises(ModelError):
        apply_overrides(m, [Override(target="nope", value=1, period=2024)])


def test_row_override_missing_period_raises():
    m = _PnL()
    with pytest.raises(ModelError):
        apply_overrides(m, [Override(target="revenue", value=1)])


# ---------------------------------------------------------------------------
# TOML I/O
# ---------------------------------------------------------------------------


def test_read_overrides_missing_file(tmp_path: Path):
    assert read_overrides(tmp_path / "missing.toml") == []


def test_write_then_read_roundtrip(tmp_path: Path):
    overrides = [
        Override(target="revenue", value=1500, period=2025, reason="signed Q1", author="pietro"),
        Override(target="revenue_growth", value=0.07, kind="glob"),
    ]
    path = tmp_path / "overrides.toml"
    write_overrides(path, overrides)
    parsed = tomllib.loads(path.read_text())
    assert len(parsed["override"]) == 2
    loaded = read_overrides(path)
    assert loaded == overrides


def test_read_invalid_toml_structure(tmp_path: Path):
    path = tmp_path / "overrides.toml"
    path.write_text("override = 42\n")
    with pytest.raises(ModelError):
        read_overrides(path)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def _model_bin() -> str:
    bin_path = Path(sys.executable).parent / "sweet"
    if not bin_path.exists():
        pytest.skip(f"Console script not installed at {bin_path}")
    return str(bin_path)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_model_bin(), *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_cli_overrides_add_list_rm(tmp_path: Path):
    proc = _run(["init", "demo"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    demo = tmp_path / "demo"

    # Add a glob override (the demo model has growth_rate)
    proc = _run(
        [
            "overrides",
            "add",
            "growth_rate",
            "",
            "0.20",
            "--glob",
            "--reason",
            "test",
        ],
        demo,
    )
    assert proc.returncode == 0, proc.stderr

    proc = _run(["overrides", "list"], demo)
    assert proc.returncode == 0, proc.stderr
    assert "growth_rate" in proc.stdout
    assert "0.2" in proc.stdout

    # Run picks up the override.
    proc = _run(["run"], demo)
    assert proc.returncode == 0, proc.stderr
    assert "1 override" in proc.stdout
    # 100 * 1.20 = 120 at year 2.
    assert "120" in proc.stdout

    # Remove it.
    proc = _run(["overrides", "rm", "growth_rate", "", "--glob"], demo)
    assert proc.returncode == 0, proc.stderr
    proc = _run(["overrides", "list"], demo)
    assert "(no overrides)" in proc.stdout
