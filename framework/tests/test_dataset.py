"""Tests for dataset.csv() and dataset.from_row() (PRD §3.6)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from expression import Model, dataset, glob, periods, row


def test_csv_dataset_load_and_last(tmp_path: Path):
    csv_path = tmp_path / "historical.csv"
    csv_path.write_text("date,revenue\n2022,100\n2023,110\n2024,125\n")

    class Forecast(Model):
        time = periods(2025, 2027)
        historical = dataset.csv(csv_path, index="date")
        rate = glob(0.05)

        @row
        def forecast(self, t):
            if t == self.time.first:
                return self.historical.last("revenue")
            return self.forecast(t - 1) * (1 + self.rate)

    m = Forecast().solve()
    assert m.cell("forecast", 2025) == 125
    assert math.isclose(m.cell("forecast", 2026), 125 * 1.05)


def test_csv_lookup(tmp_path: Path):
    csv_path = tmp_path / "fx.csv"
    csv_path.write_text("currency,usd_per_unit\nEUR,1.10\nGBP,1.27\nJPY,0.0067\n")

    class P(Model):
        time = periods(2024, 2024)
        fx = dataset.csv(csv_path, index="currency")

        @row
        def eur_to_usd(self, t):
            return self.fx.lookup("EUR", "usd_per_unit")

    m = P().solve()
    assert m.cell("eur_to_usd", 2024) == 1.10


def test_csv_missing_file(tmp_path: Path):
    class P(Model):
        time = periods(2024, 2024)
        ds = dataset.csv(tmp_path / "missing.csv")

        @row
        def x(self, t):
            return self.ds.last("foo")

    with pytest.raises(Exception, match="CSV not found"):
        P().solve()


def test_from_row_builds_dataset():
    class B(Model):
        time = periods(2024, 2026)

        @row
        def budget(self, t):
            if t == self.time.first:
                return 100
            return self.budget(t - 1) * 1.1

    m = B().solve()
    out = dataset.from_row(m, "budget", columns=["year", "value"])
    assert out.columns == ["year", "value"]
    assert out.rows[0] == {"year": 2024, "value": 100}
    assert math.isclose(out.rows[1]["value"], 110.0)
    assert math.isclose(out.rows[2]["value"], 121.0)
    assert out.lookup(2025, "value") == out.rows[1]["value"]


def test_dataset_first_and_column(tmp_path: Path):
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("k,v\n1,10\n2,20\n3,30\n")

    class P(Model):
        time = periods(2024, 2024)
        ds = dataset.csv(csv_path, index="k")

        @row
        def x(self, t):
            return self.ds.first("v") + sum(self.ds.column("v"))

    m = P().solve()
    assert m.cell("x", 2024) == 10 + 60
