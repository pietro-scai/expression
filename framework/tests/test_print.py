"""Phase 3 — display / print tests."""

from __future__ import annotations

import pytest

from sweet import Model, ModelError, glob, periods, row, scalar


class Budget(Model):
    time = periods(2024, 2026)
    seed = glob(100)
    growth_rate = glob(0.05)

    @row
    def budget(self, t):
        if t == self.time.first:
            return self.seed
        return self.budget(t - 1) * (1 + self.growth_rate)


class WithScalar(Model):
    time = periods(2024, 2026)

    @row
    def revenue(self, t):
        return 100 * (t - 2023)

    @scalar
    def total(self):
        return sum(self.revenue(t) for t in self.time)


def test_format_table_renders_periods_and_rows():
    m = Budget()
    m.solve()
    out = m.format_table()
    for t in (2024, 2025, 2026):
        assert str(t) in out
    assert "budget" in out
    assert "100" in out


def test_format_table_columns_aligned():
    m = Budget()
    m.solve()
    lines = m.format_table().splitlines()
    # All lines have the same width once rendered (padding via rjust/ljust).
    assert len({len(line) for line in lines}) == 1


def test_format_table_unsolved_raises():
    m = Budget()
    with pytest.raises(ModelError, match="not solved"):
        m.format_table()


def test_format_csv_header_and_first_row():
    m = Budget()
    m.solve()
    out = m.format_csv()
    lines = out.strip().splitlines()
    assert lines[0] == ",2024,2025,2026"
    assert lines[1].startswith("budget,")


def test_format_csv_unsolved_raises():
    m = Budget()
    with pytest.raises(ModelError, match="not solved"):
        m.format_csv()


def test_str_unsolved_terse():
    m = Budget()
    s = str(m)
    assert "not solved" in s
    assert "Budget" in s


def test_str_solved_returns_table():
    m = Budget()
    m.solve()
    assert "2024" in str(m)


def test_repr_always_terse():
    m = Budget()
    assert repr(m) == "<Budget: 1 row, 0 cells, not solved>"
    m.solve()
    assert "solved" in repr(m)
    assert "row" in repr(m)


def test_scalar_renders_in_table_block():
    m = WithScalar()
    m.solve()
    out = m.format_table()
    assert "total" in out
    assert "total = 600" in out


def test_scalar_renders_in_csv_block():
    m = WithScalar()
    m.solve()
    out = m.format_csv()
    assert "\ntotal,600" in out
