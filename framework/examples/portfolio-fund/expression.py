from expression import Model, periods, glob, row, dim, depends

# Company universe
COMPANIES = [f"Co{i + 1}" for i in range(10)]

# MOICs spread evenly 1.0x to 3.0x
MOIC_MAP = {f"Co{i + 1}": round(1.0 + i * 2.0 / 9, 2) for i in range(10)}

# Exit years staggered 2029-2034 across the 10 companies
EXIT_MAP = {f"Co{i + 1}": 2029 + (i % 6) for i in range(10)}


def _irr(cashflows):
    """IRR via bisection. Returns IRR as a % float."""
    def npv(r):
        return sum(cf / (1 + r) ** i for i, cf in enumerate(cashflows))

    try:
        lo = -0.9999
        hi = 100.0
        f_lo = npv(lo)
        f_hi = npv(hi)
        if f_lo == 0:
            return round(lo * 100, 1)
        if f_hi == 0:
            return round(hi * 100, 1)
        if f_lo * f_hi > 0:
            return 0.0
        for _ in range(100):
            mid = (lo + hi) / 2
            f_mid = npv(mid)
            if abs(f_mid) < 1e-7:
                return round(mid * 100, 1)
            if f_lo * f_mid <= 0:
                hi = mid
            else:
                lo = mid
                f_lo = f_mid
        return round(((lo + hi) / 2) * 100, 1)
    except Exception:
        return 0.0


class PortfolioModel(Model):
    """Per-company drawdown / distribution matrix."""

    time = periods(2025, 2034)

    fund_size = glob(35_000, doc="Total fund size ($M)")
    n_cos = glob(10, doc="Number of portfolio companies")
    pct_y1 = glob(0.50, doc="% of commitment called in investment year 1")
    pct_y2 = glob(0.30, doc="% of commitment called in investment year 2")
    pct_y3 = glob(0.20, doc="% of commitment called in investment year 3")

    companies = dim(COMPANIES)

    @row(over=[time, companies])
    def drawdown(self, t, companies):
        """Capital called per company ($M). Same J-curve schedule for all."""
        alloc = self.fund_size / self.n_cos
        if t == 2025:
            return alloc * self.pct_y1
        if t == 2026:
            return alloc * self.pct_y2
        if t == 2027:
            return alloc * self.pct_y3
        return 0.0

    @row(over=[time, companies])
    def distribution(self, t, companies):
        """Cash returned to LP per company at exit ($M)."""
        alloc = self.fund_size / self.n_cos
        return alloc * MOIC_MAP[companies] if t == EXIT_MAP[companies] else 0.0

    @row(over=[time, companies])
    def moic_at_exit(self, t, companies):
        """Exit MOIC shown in exit year, 0 otherwise."""
        return MOIC_MAP[companies] if t == EXIT_MAP[companies] else 0.0

    @row(over=[time, companies])
    def irr_pct(self, t, companies):
        """Company IRR % shown in exit year, 0 otherwise."""
        alloc = self.fund_size / self.n_cos
        if t != EXIT_MAP[companies]:
            return 0.0
        flows = []
        for yr in range(2025, 2035):
            cf = 0.0
            if yr == 2025:
                cf -= alloc * self.pct_y1
            if yr == 2026:
                cf -= alloc * self.pct_y2
            if yr == 2027:
                cf -= alloc * self.pct_y3
            if yr == EXIT_MAP[companies]:
                cf += alloc * MOIC_MAP[companies]
            flows.append(cf)
        return _irr(flows)

    @row
    def total_drawdown(self, t):
        """Total drawdown across all companies ($M)."""
        if t == 2025:
            return self.fund_size * self.pct_y1
        if t == 2026:
            return self.fund_size * self.pct_y2
        if t == 2027:
            return self.fund_size * self.pct_y3
        return 0.0

    @row
    def total_distribution(self, t):
        """Total distributions across all companies ($M)."""
        alloc = self.fund_size / self.n_cos
        return sum(alloc * MOIC_MAP[co] for co in COMPANIES if EXIT_MAP[co] == t)


class FundModel(Model):
    """Fund-level simulation: fees, NAV, cumulative MOIC and IRR."""

    time = periods(2025, 2034)

    portfolio = depends(PortfolioModel)
    fund_size = glob(35_000, doc="Total fund size ($M)")
    mgmt_fee_pct = glob(0.015, doc="Annual mgmt fee % of committed capital")

    @row
    def drawn(self, t):
        """Capital called from LPs each year ($M)."""
        return self.portfolio.total_drawdown(t)

    @row
    def distributed(self, t):
        """Cash returned to LPs each year ($M)."""
        return self.portfolio.total_distribution(t)

    @row
    def mgmt_fee(self, t):
        """Annual management fee ($M)."""
        return self.fund_size * self.mgmt_fee_pct

    @row
    def net_cf(self, t):
        """Net fund cash flow after fees ($M). Negative = LP outflow."""
        return (
            self.portfolio.total_distribution(t)
            - self.portfolio.total_drawdown(t)
            - self.fund_size * self.mgmt_fee_pct
        )

    @row
    def cum_drawn(self, t):
        """Cumulative capital called ($M)."""
        return sum(self.portfolio.total_drawdown(yr) for yr in range(2025, t + 1))

    @row
    def cum_distributed(self, t):
        """Cumulative distributions ($M)."""
        return sum(self.portfolio.total_distribution(yr) for yr in range(2025, t + 1))

    @row
    def nav(self, t):
        """NAV = cumulative drawn - cumulative distributed ($M)."""
        return self.cum_drawn(t) - self.cum_distributed(t)

    @row
    def fund_moic(self, t):
        """Cumulative MOIC = total distributed / total drawn."""
        cd = self.cum_drawn(t)
        return round(self.cum_distributed(t) / cd, 2) if cd else 0.0

    @row
    def fund_irr(self, t):
        """Fund IRR % on net cash flows to date (0 before first exit in 2029)."""
        if t < 2029:
            return 0.0
        flows = [
            self.portfolio.total_distribution(yr)
            - self.portfolio.total_drawdown(yr)
            - self.fund_size * self.mgmt_fee_pct
            for yr in range(2025, t + 1)
        ]
        return _irr(flows)
