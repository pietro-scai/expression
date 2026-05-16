"""Tests for cross-model composition via depends() (PRD §3.8 / example 12.6)."""

from __future__ import annotations

import math

import pytest

from sweet import Model, ModelError, depends, glob, periods, row


class Costs(Model):
    time = periods(2024, 2026)
    fixed = glob(100)

    @row
    def total_cost(self, t):
        return self.fixed * (t - self.time.first + 1)


class PnL(Model):
    time = periods(2024, 2026)
    revenue_growth = glob(0.10)
    costs = depends(Costs)

    @row
    def revenue(self, t):
        if t == self.time.first:
            return 1000
        return self.revenue(t - 1) * (1 + self.revenue_growth)

    @row
    def margin(self, t):
        return self.revenue(t) - self.costs.total_cost(t)


def test_depends_cell_access():
    m = PnL()
    m.solve()
    assert math.isclose(m.cell("revenue", 2024), 1000)
    assert math.isclose(m.cell("margin", 2024), 1000 - 100)
    assert math.isclose(m.cell("margin", 2025), 1100 - 200)
    assert math.isclose(m.cell("margin", 2026), 1210 - 300)


def test_depends_solves_upstream_lazily():
    m = PnL()
    upstream = m.costs
    assert upstream.cell("total_cost", 2024) == 100
    assert m.costs is upstream  # cached


def test_depends_circular_detected():
    """A cycle across model classes is caught when the cycle-closing dep is defined.

    Python forces a definition order, so we build A first, then B(depends A), then
    inject a back-edge A→B by mutating ``A._depends`` and re-running the check.
    """
    from sweet.core import Depends, _check_cross_model_cycle

    class CycA(Model):
        time = periods(2024, 2025)

        @row
        def x(self, t):
            return 1

    class CycB(Model):
        time = periods(2024, 2025)
        a = depends(CycA)

        @row
        def y(self, t):
            return self.a.x(t)

    back_edge = Depends(CycB)
    back_edge._name = "b"
    CycA._depends = {**CycA._depends, "b": back_edge}
    with pytest.raises(ModelError, match="Circular cross-model"):
        _check_cross_model_cycle(CycA)


def test_depends_only_accepts_model_subclass():
    with pytest.raises(TypeError):

        class _Bad(Model):
            time = periods(2024, 2025)
            x = depends(int)  # type: ignore[arg-type]
