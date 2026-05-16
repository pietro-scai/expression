"""Phase 0 end-to-end tests, including PRD example 12.1."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from sweet import (
    Model,
    ModelError,
    glob,
    periods,
    row,
)

# ---------------------------------------------------------------------------
# PRD example 12.1 — the "hello world" budget model (Layer 1 form).
# ---------------------------------------------------------------------------


class Budget(Model):
    time = periods(2024, 2028)
    seed = glob(100, doc="Starting budget in $K")
    growth_rate = glob(0.05, doc="Annual growth rate")

    @row
    def budget(self, t):
        if t == self.time.first:
            return self.seed
        return self.budget(t - 1) * (1 + self.growth_rate)


MODULE_GROWTH_RATE = 0.07


class ModuleGlobalBudget(Model):
    time = periods(2024, 2025)

    @row
    def seed(self, t):
        return 100

    @row
    def budget(self, t):
        local_adjustment = 1
        return self.seed(t) * (1 + MODULE_GROWTH_RATE) + local_adjustment + math.floor(0.1)


def test_example_12_1_budget_solve():
    m = Budget()
    m.solve()
    series = m.series("budget")
    expected = [100.0, 105.0, 110.25, 115.7625, 121.550625]
    assert len(series) == len(expected)
    for got, want in zip(series, expected, strict=True):
        assert math.isclose(got, want, rel_tol=1e-12)


def test_example_12_1_show_specific_cell():
    m = Budget()
    m.solve()
    assert math.isclose(m._cells[("budget", 2026)], 110.25, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Multi-row dependency (PRD example 12.2 — adapted to Layer 1).
# ---------------------------------------------------------------------------


class PnL(Model):
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


def test_multi_row_dependency_topo_order():
    m = PnL()
    m.solve()
    expected_rev = [1000, 1100.0, 1000 * 1.1 * 1.1]
    for got, want in zip(m.series("revenue"), expected_rev, strict=True):
        assert math.isclose(got, want, rel_tol=1e-12)
    for t in m.time:
        rev = m._cells[("revenue", t)]
        assert math.isclose(m._cells[("gross_profit", t)], rev * 0.6, rel_tol=1e-12)


def test_multi_row_topo_sort_picks_rev_before_gross_profit():
    import networkx as nx

    from sweet.solver import build_dag

    m = PnL()
    g = build_dag(m)
    order = list(nx.topological_sort(g))
    assert order.index("revenue") < order.index("cogs")
    assert order.index("cogs") < order.index("gross_profit")
    assert order.index("revenue") < order.index("gross_profit")


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_missing_periods_raises():
    class NoTime(Model):
        @row
        def foo(self, t):
            return 1

    with pytest.raises(ModelError):
        NoTime().solve()


def test_circular_dependency_between_rows_detected():
    class Cyclic(Model):
        time = periods(2024, 2025)

        @row
        def a(self, t):
            return self.b(t)

        @row
        def b(self, t):
            return self.a(t)

    with pytest.raises(ModelError, match="Circular"):
        Cyclic().solve()


def test_cell_level_circular_reference_detected():
    """A row that asks for its own current period (not a lag) is a true cycle."""

    class SelfCycle(Model):
        time = periods(2024, 2025)

        @row
        def x(self, t):
            return self.x(t) + 1  # asks for itself at t

    m = SelfCycle()
    with pytest.raises(ModelError):
        m.solve()


def test_glob_default_and_override():
    m = Budget()
    assert m.growth_rate == 0.05
    m.growth_rate = 0.20
    assert m.growth_rate == 0.20
    m.solve()
    series = m.series("budget")
    assert math.isclose(series[1], 120.0, rel_tol=1e-12)


def test_describe_tracks_module_global_dependencies():
    from sweet.output import describe_model

    desc = describe_model(ModuleGlobalBudget())
    model = desc["models"][0]
    budget_def = next(r for r in model["rows"] if r["name"] == "budget")
    assert set(budget_def["depends_on"]) == {"MODULE_GROWTH_RATE", "seed"}
    assert {"name": "MODULE_GROWTH_RATE", "kind": "glob"} in model["dag"]["nodes"]
    assert {"from": "MODULE_GROWTH_RATE", "to": "budget"} in model["dag"]["edges"]


def test_periods_basic():
    p = periods(2024, 2028)
    assert p.first == 2024
    assert p.last == 2028
    assert list(p) == [2024, 2025, 2026, 2027, 2028]
    assert 2026 in p
    assert 2030 not in p
    assert len(p) == 5


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


def _model_bin() -> str:
    """Return the installed `model` console script path.

    The console script is used (not ``python -m model.cli``) because the user's
    ``model.py`` lives in cwd and would shadow our top-level ``model`` package
    when invoked via ``-m``. The console script in ``venv/bin/`` does not put
    cwd on sys.path, so the package import resolves correctly.
    """
    bin_path = Path(sys.executable).parent / "sweet"
    if not bin_path.exists():
        pytest.skip(f"Console script not installed at {bin_path}")
    return str(bin_path)


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_model_bin(), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_init_run_show(tmp_path: Path):
    proc = _run_cli(["init", "demo"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    demo = tmp_path / "demo"
    assert (demo / "sweet.py").exists()
    assert (demo / "sweet.md").exists()

    proc = _run_cli(["run"], demo)
    assert proc.returncode == 0, proc.stderr
    assert "Solved" in proc.stdout
    result = json.loads((demo / "outputs" / "result.json").read_text())
    # result.json now uses the multi-model shape: {"models": [...]}
    model_entry = result["models"][0]
    budget = next(t for t in model_entry["tables"] if t["name"] == "budget")
    assert math.isclose(budget["results"]["2024"], 100.0, rel_tol=1e-12)
    assert math.isclose(budget["results"]["2025"], 105.0, rel_tol=1e-12)
    assert model_entry["model"]["name"] == "Demo"
    assert model_entry["inputs"]["seed"]["value"] == 100

    proc = _run_cli(["show", "budget[2026]"], demo)
    assert proc.returncode == 0, proc.stderr
    assert "budget[2026]" in proc.stdout
    assert "110.25" in proc.stdout

    proc = _run_cli(["show", "budget"], demo)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("budget[") == 5

    proc = _run_cli(["describe"], demo)
    assert proc.returncode == 0, proc.stderr
    desc = json.loads((demo / "outputs" / "model.json").read_text())
    assert desc["models"][0]["name"] == "Demo"
    assert "seed" in desc["models"][0]["globals"]
    budget_def = next(r for r in desc["models"][0]["rows"] if r["name"] == "budget")
    assert "def budget" in budget_def["source"]
    assert set(budget_def["depends_on"]) >= {"seed", "growth_rate"}
    edges = desc["models"][0]["dag"]["edges"]
    assert {"from": "seed", "to": "budget"} in edges
    assert desc["models"][0]["mermaid"].startswith("graph TD")
    assert desc["documentation"] is not None
