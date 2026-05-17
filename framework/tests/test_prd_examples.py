"""End-to-end tests reproducing PRD §12.2-12.5 worked examples.

These exist to anchor Phase 1 to the PRD's contract: if any of them break,
the PRD example would fail.
"""

from __future__ import annotations

import math
from pathlib import Path

from expression import Model, dataset, dim, glob, matrix, periods, row, scalar, xl

# ---------------------------------------------------------------------------
# PRD 12.2 — Multi-row dependency
# ---------------------------------------------------------------------------


class PRD12_2(Model):
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


def test_prd_12_2_pnl():
    m = PRD12_2().solve()
    assert math.isclose(m.cell("revenue", 2024), 1000)
    assert math.isclose(m.cell("revenue", 2025), 1100)
    assert math.isclose(m.cell("revenue", 2026), 1210)
    assert math.isclose(m.cell("gross_profit", 2024), 600)
    assert math.isclose(m.cell("gross_profit", 2026), 1210 * 0.6)


# ---------------------------------------------------------------------------
# PRD 12.3 — Override
# ---------------------------------------------------------------------------


def test_prd_12_3_override():
    from expression.overrides import Override, apply_overrides

    m = PRD12_2()
    apply_overrides(m, [Override(target="revenue", value=1500, period=2025)])
    m.solve()
    rev = m.series("revenue")
    assert rev[0] == 1000
    assert rev[1] == 1500
    assert math.isclose(rev[2], 1650.0, rel_tol=1e-9)  # 1500 * 1.10


# ---------------------------------------------------------------------------
# PRD 12.4 — Lookup against dataset, multi-dim row over (products, time)
# ---------------------------------------------------------------------------


def test_prd_12_4_pricing(tmp_path: Path):
    csv_path = tmp_path / "fx.csv"
    csv_path.write_text("currency,usd_per_unit\nEUR,1.10\n")

    class Pricing(Model):
        fx = dataset.csv(csv_path, index="currency")
        products = dim(["A", "B"])
        time = periods(2024, 2026)

        base_price_eur = matrix(products, default={"A": 10, "B": 25})

        @row(over=[products, time])
        def price_usd(self, p, t):
            return self.base_price_eur[p] * self.fx.lookup("EUR", "usd_per_unit")

    m = Pricing().solve()
    assert math.isclose(m.cell("price_usd", ("A", 2024)), 10 * 1.10)
    assert math.isclose(m.cell("price_usd", ("B", 2026)), 25 * 1.10)


# ---------------------------------------------------------------------------
# PRD 12.5 — Investment with IRR / NPV / MOIC / payback
# ---------------------------------------------------------------------------


class PRD12_5(Model):
    time = periods(2024, 2031)
    initial_investment = glob(5_000_000)
    discount_rate = glob(0.12)
    exit_multiple = glob(2.5)

    @row
    def cash_flow():
        cash_flow[first] = -initial_investment
        cash_flow[2025] = 200_000
        cash_flow[2026] = 500_000
        cash_flow[2027] = 800_000
        cash_flow[2028] = 1_200_000
        cash_flow[2029] = 1_500_000
        cash_flow[2030] = 1_800_000
        cash_flow[last] = 2_000_000 + initial_investment * exit_multiple

    @row
    def cumulative():
        cumulative[first] = cash_flow[first]
        cumulative[n] = cumulative[n - 1] + cash_flow[n]

    @scalar
    def npv():
        return cash_flow[first] + xl.npv(discount_rate, cash_flow[2025:2031])

    @scalar
    def moic():
        return xl.sum(cash_flow[2025:2031]) / -cash_flow[first]


def test_prd_12_5_deal_returns():
    m = PRD12_5().solve()
    cash = m.series("cash_flow")
    assert cash[0] == -5_000_000
    assert cash[-1] == 2_000_000 + 5_000_000 * 2.5  # 14_500_000
    cum = m.series("cumulative")
    assert cum[0] == -5_000_000
    # cumulative[2030] still negative (around -800k); cumulative[2031] strongly positive.
    assert cum[-1] > 0
    npv = m.cell("npv", None)
    # Sanity check: positive NPV at this profile and 12% discount.
    assert npv > 0
    moic = m.cell("moic", None)
    assert math.isclose(
        moic, sum(cash[1:]) / 5_000_000, rel_tol=1e-9
    )
    # MOIC should exceed 4x given the exit value.
    assert moic > 4.0
