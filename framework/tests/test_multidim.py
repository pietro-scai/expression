"""Tests for dim(), matrix(), and multi-dim @row(over=...)."""

from __future__ import annotations

import math

from expression import Model, dim, matrix, periods, row


class Pricing(Model):
    products = dim(["A", "B", "C"])
    regions = dim(["EU", "US"])
    time = periods(2024, 2025)

    base_price = matrix(products, regions, default=10.0)
    tax_rate = matrix(regions, time, default=0.2)

    @row(over=[products, regions, time])
    def revenue(self, p, r, t):
        return self.base_price[p, r] * (1 + self.tax_rate[r, t])


def test_multidim_default_values():
    m = Pricing().solve()
    for p in ["A", "B", "C"]:
        for r in ["EU", "US"]:
            for t in [2024, 2025]:
                assert math.isclose(m.cell("revenue", (p, r, t)), 10.0 * 1.2)


def test_matrix_override():
    m = Pricing()
    m.base_price["A", "EU"] = 25.0
    m.tax_rate["US", 2025] = 0.30
    m.solve()
    assert math.isclose(m.cell("revenue", ("A", "EU", 2024)), 25.0 * 1.2)
    assert math.isclose(m.cell("revenue", ("A", "EU", 2025)), 25.0 * 1.2)
    assert math.isclose(m.cell("revenue", ("B", "US", 2025)), 10.0 * 1.30)


def test_dim_iteration():
    products = dim(["A", "B", "C"])
    assert list(products) == ["A", "B", "C"]
    assert "B" in products
    assert "Z" not in products
    assert len(products) == 3


def test_matrix_dict_default_for_1d():
    """PRD example 12.4 uses ``default={'A': 10, 'B': 25}`` for a 1-D matrix."""

    class P(Model):
        products = dim(["A", "B"])
        time = periods(2024, 2025)
        base_price_eur = matrix(products, default={"A": 10, "B": 25})

        @row(over=[products, time])
        def price(self, p, t):
            return self.base_price_eur[p]

    m = P().solve()
    assert m.cell("price", ("A", 2024)) == 10
    assert m.cell("price", ("B", 2025)) == 25
