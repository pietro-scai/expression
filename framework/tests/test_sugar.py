"""Tests for the Layer-2 AST sugar (PRD §3.3, §3.5)."""

from __future__ import annotations

import math

import pytest

from expression import Model, ModelError, glob, periods, row, scalar, xl

# ---------------------------------------------------------------------------
# PRD example 12.1 in Layer 2 form.
# ---------------------------------------------------------------------------


class BudgetSugar(Model):
    time = periods(2024, 2028)
    seed = glob(100)
    growth_rate = glob(0.05)

    @row
    def budget():
        budget[first] = seed
        budget[n] = budget[n - 1] * (1 + growth_rate)


def test_layer2_basic_budget():
    m = BudgetSugar().solve()
    series = m.series("budget")
    expected = [100.0, 105.0, 110.25, 115.7625, 121.550625]
    for got, want in zip(series, expected, strict=True):
        assert math.isclose(got, want, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# PRD example 12.2 in Layer 2 form (multi-row).
# ---------------------------------------------------------------------------


class PnLSugar(Model):
    time = periods(2024, 2026)
    revenue_growth = glob(0.10)
    cogs_pct = glob(0.40)

    @row
    def revenue():
        revenue[first] = 1000
        revenue[n] = revenue[n - 1] * (1 + revenue_growth)

    @row
    def cogs():
        cogs[t] = revenue[t] * cogs_pct

    @row
    def gross_profit():
        gross_profit[t] = revenue[t] - cogs[t]


def test_layer2_pnl_multi_row():
    m = PnLSugar().solve()
    rev = m.series("revenue")
    assert math.isclose(rev[0], 1000)
    assert math.isclose(rev[1], 1100)
    assert math.isclose(rev[2], 1210)
    for t in m.time:
        assert math.isclose(m.cell("gross_profit", t), m.cell("revenue", t) * 0.6)


# ---------------------------------------------------------------------------
# Layer 2 explicit per-period rules (PRD example 12.5 cash_flow shape).
# ---------------------------------------------------------------------------


class Investment(Model):
    time = periods(2024, 2026)
    seed = glob(-100)

    @row
    def cash_flow():
        cash_flow[first] = seed
        cash_flow[2025] = 50
        cash_flow[last] = 200


def test_layer2_explicit_periods():
    m = Investment().solve()
    assert m.cell("cash_flow", 2024) == -100
    assert m.cell("cash_flow", 2025) == 50
    assert m.cell("cash_flow", 2026) == 200


# ---------------------------------------------------------------------------
# Layer 2 with @scalar + xl.
# ---------------------------------------------------------------------------


class ScalarSugar(Model):
    time = periods(2024, 2026)
    rate = glob(0.10)

    @row
    def cash_flow():
        cash_flow[first] = -1000
        cash_flow[2025] = 600
        cash_flow[last] = 600

    @scalar
    def total():
        return xl.sum(cash_flow[:])


def test_layer2_scalar_with_series():
    m = ScalarSugar().solve()
    assert m.cell("total", None) == 200


# ---------------------------------------------------------------------------
# Layer 2 inclusive window slice.
# ---------------------------------------------------------------------------


class WindowSugar(Model):
    time = periods(2024, 2028)

    @row
    def x():
        x[t] = t - 2024  # 0,1,2,3,4

    @scalar
    def mid_window():
        return xl.sum(x[2025:2027])


def test_layer2_inclusive_window():
    m = WindowSugar().solve()
    # 2025..2027 inclusive: values 1+2+3 = 6
    assert m.cell("mid_window", None) == 6.0


# ---------------------------------------------------------------------------
# Sugar opt-out at class scope.
# ---------------------------------------------------------------------------


class NoSugar(Model, sugar=False):
    time = periods(2024, 2025)

    @row
    def x(self, t):
        return 42


def test_sugar_opt_out_layer1_passes_through():
    m = NoSugar().solve()
    assert m.cell("x", 2024) == 42
    assert m.cell("x", 2025) == 42


def test_sugar_opt_out_layer2_form_fails_to_run():
    """With sugar disabled, a Layer-2-shaped function is a regular Python function."""

    with pytest.raises((TypeError, ModelError)):
        # bare `name[first]` doesn't resolve at runtime without sugar.
        class _BadNoSugar(Model, sugar=False):
            time = periods(2024, 2025)

            @row
            def y():  # type: ignore[no-untyped-def]
                y[first] = 1

        _BadNoSugar().solve()


# ---------------------------------------------------------------------------
# Mix Layer 1 and Layer 2 in the same class.
# ---------------------------------------------------------------------------


class MixedLayers(Model):
    time = periods(2024, 2026)
    base = glob(10)

    @row
    def a(self, t):  # Layer 1
        return self.base * (t - self.time.first + 1)

    @row
    def b():  # Layer 2
        b[t] = a[t] * 2


def test_layer1_and_layer2_coexist():
    m = MixedLayers().solve()
    for i, t in enumerate(m.time, start=1):
        assert m.cell("a", t) == 10 * i
        assert m.cell("b", t) == 20 * i
