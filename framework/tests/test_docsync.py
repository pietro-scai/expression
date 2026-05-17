"""Doc sync (Phase 3, PRD §6)."""

from __future__ import annotations

from expression import Model, glob, periods, row, scalar, xl
from expression.docsync import compare, extract_md_mentions, format_drift


class _M(Model):
    time = periods(2024, 2026)
    growth_rate = glob(0.05)

    @row
    def revenue(self, t):
        return 100 if t == self.time.first else self.revenue(t - 1) * (1 + self.growth_rate)

    @scalar
    def total(self):
        return xl.sum(self.series("revenue"))


def test_extract_md_mentions() -> None:
    md = "see `revenue[2024]` and `growth_rate`. Plain `English` text."
    found = extract_md_mentions(md)
    assert {"revenue", "growth_rate", "English"} <= found


def test_compare_in_sync() -> None:
    md = "Inputs: `growth_rate`. Output: `revenue[year]`. Scalar: `total`."
    drift = compare(_M(), md)
    assert drift.empty
    assert format_drift(drift) == "✓ expression.md is in sync with expression.py"


def test_compare_drift_in_code_not_md() -> None:
    md = "Only mentions `revenue[year]`."
    drift = compare(_M(), md)
    assert "growth_rate" in drift.in_code_not_md
    assert "total" in drift.in_code_not_md
    text = format_drift(drift)
    assert "growth_rate" in text


def test_compare_drift_in_md_not_code() -> None:
    md = "Mentions `revenue[year]`, `growth_rate`, `total`, and a missing `cogs[2024]`."
    drift = compare(_M(), md)
    assert drift.in_md_not_code == ["cogs"]
