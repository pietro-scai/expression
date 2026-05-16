"""Tests for @scalar rows and the xl.* namespace."""

from __future__ import annotations

import math

import pytest

from sweet import Model, ModelError, glob, periods, register, row, scalar, xl

# ---------------------------------------------------------------------------
# @scalar basics
# ---------------------------------------------------------------------------


class _DealReturns(Model):
    time = periods(2024, 2031)
    initial_investment = glob(5_000_000)
    discount_rate = glob(0.12)
    exit_multiple = glob(2.5)

    @row
    def cash_flow(self, t):
        if t == self.time.first:
            return -self.initial_investment
        if t == self.time.last:
            return 2_000_000 + self.initial_investment * self.exit_multiple
        offsets = {2025: 200_000, 2026: 500_000, 2027: 800_000, 2028: 1_200_000, 2029: 1_500_000, 2030: 1_800_000}
        return offsets[t]

    @row
    def cumulative(self, t):
        if t == self.time.first:
            return self.cash_flow(t)
        return self.cumulative(t - 1) + self.cash_flow(t)

    @scalar
    def npv(self):
        return self.cash_flow(self.time.first) + xl.npv(
            self.discount_rate, self.series("cash_flow")[1:]
        )

    @scalar
    def moic(self):
        return xl.sum(self.series("cash_flow")[1:]) / -self.cash_flow(self.time.first)


def test_scalar_runs_after_rows():
    m = _DealReturns().solve()
    cumulative = m.series("cumulative")
    assert cumulative[0] == -5_000_000
    assert m.cell("npv", None) > 0
    moic = m.cell("moic", None)
    assert math.isclose(moic, (200_000 + 500_000 + 800_000 + 1_200_000 + 1_500_000 + 1_800_000 + 14_500_000) / 5_000_000)


def test_scalar_circular_detected():
    class Bad(Model):
        time = periods(2024, 2025)

        @row
        def x(self, t):
            return 1

        @scalar
        def a(self):
            return self.b()

        @scalar
        def b(self):
            return self.a()

    with pytest.raises(ModelError):
        Bad().solve()


# ---------------------------------------------------------------------------
# xl.* basics
# ---------------------------------------------------------------------------


def test_xl_statistics():
    assert xl.sum([1, 2, 3]) == 6.0
    assert xl.avg([1, 2, 3, 4]) == 2.5
    assert xl.min([3, 1, 2]) == 1.0
    assert xl.max([3, 1, 2]) == 3.0
    assert xl.median([1, 2, 3, 4, 5]) == 3.0
    assert math.isclose(xl.percentile([1, 2, 3, 4], 0.5), 2.5)


def test_xl_logical():
    assert xl.if_(True, "a", "b") == "a"
    assert xl.if_(False, "a", "b") == "b"
    assert xl.and_(True, True, True) is True
    assert xl.and_(True, False) is False
    assert xl.or_(False, False, True) is True
    assert xl.not_(False) is True
    assert xl.iferror(lambda: 1 / 0, "fallback") == "fallback"
    assert xl.iferror(lambda: 42, "fallback") == 42


def test_xl_npv():
    npv = xl.npv(0.10, [100, 100, 100])
    expected = 100 / 1.10 + 100 / 1.21 + 100 / 1.331
    assert math.isclose(npv, expected, rel_tol=1e-12)


def test_xl_irr():
    cf = [-1000, 300, 400, 500]
    r = xl.irr(cf)
    npv = sum(c / (1 + r) ** i for i, c in enumerate(cf))
    assert abs(npv) < 1e-6


def test_xl_pmt():
    p = xl.pmt(0.05 / 12, 360, 200_000)
    assert -1100 < p < -1070


def test_xl_cumsum_and_running_max():
    assert xl.cumsum([1, 2, 3]) == [1.0, 3.0, 6.0]
    assert xl.running_max([1, 3, 2, 5, 4]) == [1.0, 3.0, 3.0, 5.0, 5.0]


def test_xl_first_where():
    idx = xl.first_where([-3, -1, 0, 2, 5], lambda x: x >= 0)
    assert idx == 2
    assert xl.first_where([1, 2, 3], lambda x: x > 99) is None


def test_xl_register():
    @register
    def squared(x):
        return x * x

    assert xl.squared(3) == 9
    assert xl._registry["squared"] is squared
