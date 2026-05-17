"""Tests for multi-model support: same-file discovery, topo ordering, combined output."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from expression import Model, depends, glob, periods, row, scalar
from expression.core import ModelError
from expression.output import describe_models, to_json, to_json_multi
from expression.snapshot import serialize_cells, serialize_cells_multi


# ---------------------------------------------------------------------------
# fixture models
# ---------------------------------------------------------------------------


class Alpha(Model):
    """Upstream leaf model."""

    time = periods(2024, 2026)
    base = glob(100.0)

    @row
    def value(self, t):
        if t == self.time.first:
            return self.base
        return self.value(t - 1) * 1.1


class Beta(Model):
    """Midstream model that depends on Alpha."""

    time = periods(2024, 2026)
    alpha = depends(Alpha)
    markup = glob(0.2)

    @row
    def revenue(self, t):
        return self.alpha.value(t) * (1 + self.markup)


class Gamma(Model):
    """Root model that depends on both Alpha and Beta."""

    time = periods(2024, 2026)
    alpha = depends(Alpha)
    beta = depends(Beta)

    @row
    def margin(self, t):
        return self.beta.revenue(t) - self.alpha.value(t)

    @scalar
    def total_margin(self):
        return sum(self.margin(t) for t in self.time)


class Independent(Model):
    """Model with no dependency on others."""

    time = periods(2024, 2025)
    rate = glob(0.05)

    @row
    def cost(self, t):
        return 500 * (1 + self.rate) ** (t - self.time.first)


# ---------------------------------------------------------------------------
# single-model baseline
# ---------------------------------------------------------------------------


def test_single_model_solve():
    m = Alpha()
    m.solve()
    assert m.cell("value", 2024) == 100.0
    assert round(m.cell("value", 2025), 6) == round(110.0, 6)


# ---------------------------------------------------------------------------
# to_json_multi
# ---------------------------------------------------------------------------


def test_to_json_multi_structure():
    a = Alpha()
    a.solve()
    b = Independent()
    b.solve()
    result = to_json_multi([a, b])
    assert "models" in result
    assert len(result["models"]) == 2
    names = [entry["model"]["name"] for entry in result["models"]]
    assert "Alpha" in names
    assert "Independent" in names


def test_to_json_multi_single():
    a = Alpha()
    a.solve()
    result = to_json_multi([a])
    assert len(result["models"]) == 1
    assert result["models"][0]["model"]["name"] == "Alpha"


def test_to_json_multi_tables_present():
    a = Alpha()
    a.solve()
    result = to_json_multi([a])
    tables = result["models"][0]["tables"]
    assert any(t["name"] == "value" for t in tables)


def test_to_json_multi_scalars():
    g = Gamma()
    g.solve()
    result = to_json_multi([g])
    scalars = result["models"][0]["scalars"]
    assert any(s["name"] == "total_margin" for s in scalars)


# ---------------------------------------------------------------------------
# describe_models
# ---------------------------------------------------------------------------


def test_describe_models_structure():
    a = Alpha()
    b = Beta()
    out = describe_models([a, b])
    assert "models" in out
    assert len(out["models"]) == 2
    names = [m["name"] for m in out["models"]]
    assert "Alpha" in names
    assert "Beta" in names


def test_describe_models_has_dag():
    a = Alpha()
    out = describe_models([a])
    dag = out["models"][0]["dag"]
    assert "nodes" in dag
    assert "edges" in dag


def test_describe_models_has_mermaid():
    a = Alpha()
    out = describe_models([a])
    assert "graph TD" in out["models"][0]["mermaid"]


def test_describe_model_shim():
    """describe_model() still works as a single-model shim."""
    from expression.output import describe_model

    a = Alpha()
    out = describe_model(a)
    assert len(out["models"]) == 1
    assert out["models"][0]["name"] == "Alpha"


# ---------------------------------------------------------------------------
# serialize_cells_multi
# ---------------------------------------------------------------------------


def test_serialize_cells_multi_prefixes():
    a = Alpha()
    a.solve()
    b = Independent()
    b.solve()
    cells = serialize_cells_multi([a, b])
    assert all(k.startswith("Alpha.") or k.startswith("Independent.") for k in cells)
    assert "Alpha.value[2024]" in cells
    assert "Independent.cost[2024]" in cells


def test_serialize_cells_single_no_prefix():
    a = Alpha()
    a.solve()
    cells = serialize_cells(a)
    assert "value[2024]" in cells
    assert not any(k.startswith("Alpha.") for k in cells)


# ---------------------------------------------------------------------------
# _topo_sort_models (via _load_all_models via a temp file)
# ---------------------------------------------------------------------------


def _write_temp_model(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "expression.py"
    p.write_text(textwrap.dedent(source))
    return p


def test_topo_sort_via_loader(tmp_path):
    """Models with depends() are solved in dependency order."""
    src = """
    from expression import Model, glob, periods, row, depends

    class Upstream(Model):
        time = periods(2024, 2025)
        base = glob(10.0)

        @row
        def val(self, t):
            return self.base * (t - self.time.first + 1)

    class Downstream(Model):
        time = periods(2024, 2025)
        up = depends(Upstream)

        @row
        def doubled(self, t):
            return self.up.val(t) * 2
    """
    model_path = _write_temp_model(tmp_path, src)
    from expression.cli import _load_all_models

    models = _load_all_models(model_path)
    assert len(models) == 2
    names = [type(m).__name__ for m in models]
    assert names.index("Upstream") < names.index("Downstream")


def test_two_independent_models_both_loaded(tmp_path):
    """Two unrelated models are both discovered and returned."""
    src = """
    from expression import Model, glob, periods, row

    class ModelA(Model):
        time = periods(2024, 2025)
        @row
        def x(self, t): return t

    class ModelB(Model):
        time = periods(2024, 2025)
        @row
        def y(self, t): return t * 2
    """
    model_path = _write_temp_model(tmp_path, src)
    from expression.cli import _load_all_models

    models = _load_all_models(model_path)
    assert len(models) == 2
    names = {type(m).__name__ for m in models}
    assert names == {"ModelA", "ModelB"}


def test_circular_cross_model_raises(tmp_path):
    """A circular depends() chain raises ModelError with cycle info."""
    src = """
    from expression import Model, glob, periods, row
    from expression.core import Depends, _check_cross_model_cycle, ModelError

    class CycA(Model):
        time = periods(2024, 2025)
        @row
        def x(self, t): return 1

    class CycB(Model):
        time = periods(2024, 2025)
        @row
        def y(self, t): return 1

    # inject a back-edge to create a cycle for testing the CLI-level detection
    from expression.core import Depends
    CycA._depends = {"b": Depends(CycB)}
    CycB._depends = {"a": Depends(CycA)}
    """
    model_path = _write_temp_model(tmp_path, src)
    from expression.cli import _load_all_models

    with pytest.raises(ModelError, match="Circular dependency between models"):
        _load_all_models(model_path)


# ---------------------------------------------------------------------------
# combined run: solve all + combined output JSON
# ---------------------------------------------------------------------------


def test_combined_solve_and_output():
    """Solve multiple models and verify combined output structure."""
    a = Alpha()
    a.solve()
    i = Independent()
    i.solve()
    out = to_json_multi([a, i])
    assert len(out["models"]) == 2
    model_names = {entry["model"]["name"] for entry in out["models"]}
    assert model_names == {"Alpha", "Independent"}
    for entry in out["models"]:
        assert "tables" in entry
        assert "inputs" in entry
        assert "scalars" in entry


# ---------------------------------------------------------------------------
# overrides with model scoping
# ---------------------------------------------------------------------------


def test_override_model_scope(tmp_path):
    """Override scoped to ModelA does not affect ModelB."""
    from expression.overrides import Override, apply_overrides

    class MA(Model):
        time = periods(2024, 2025)
        rate = glob(0.0)

        @row
        def val(self, t):
            return 100 * (1 + self.rate) ** (t - self.time.first)

    class MB(Model):
        time = periods(2024, 2025)
        rate = glob(0.0)

        @row
        def val(self, t):
            return 200 * (1 + self.rate) ** (t - self.time.first)

    ov = Override(target="rate", value=0.1, kind="glob", model="MA")

    ma = MA()
    mb = MB()

    # Apply scoped override only to MA
    ovs_for_ma = [o for o in [ov] if o.model is None or o.model == "MA"]
    ovs_for_mb = [o for o in [ov] if o.model is None or o.model == "MB"]

    apply_overrides(ma, ovs_for_ma)
    apply_overrides(mb, ovs_for_mb)
    ma.solve()
    mb.solve()

    # MA gets the override: 100 * 1.1 at t=2025
    assert round(ma.cell("val", 2025), 6) == round(110.0, 6)
    # MB not affected: still 200
    assert mb.cell("val", 2024) == 200.0
    assert mb.cell("val", 2025) == 200.0
