from expression import Model, periods, glob, row, dim, matrix


class LovableInvestment(Model):
    """
    Lovable Investment Return Forecast (2026-2030).
    Entry: Series B @ $6.6B valuation, ~$400M ARR (Feb 2026).
    Uses a 'scenarios' dimension for Bear / Base / Bull.
    """

    time      = periods(2026, 2030)
    scenarios = dim(["Bear", "Base", "Bull"])

    # ── Your Investment ──────────────────────────────────────────────────
    investment_usd  = glob(100_000, doc="Amount invested at Series B ($)")
    entry_valuation = glob(6_600,   doc="Series B valuation at entry ($M)")
    arr_at_entry    = glob(400,     doc="Lovable ARR at time of investment ($M) — Feb 2026")

    # ── Per-scenario assumptions (matrix = dim-keyed) ────────────────────
    # Annual ARR growth: Bear 60%, Base 100%, Bull 150%
    arr_growth_rate = matrix(scenarios, default={"Bear": 0.60, "Base": 1.00, "Bull": 1.50})

    # Exit ARR multiple: Bear 15x, Base 25x, Bull 40x
    exit_multiple = matrix(scenarios, default={"Bear": 15, "Base": 25, "Bull": 40})

    # ── ARR trajectory ───────────────────────────────────────────────────
    @row(over=[time, scenarios])
    def arr(self, t, scenario):
        """Lovable ARR ($M) by year and scenario."""
        g = self.arr_growth_rate[scenario]
        if t == self.time.first:
            return self.arr_at_entry * (1 + g)
        return self.arr(t - 1, scenario) * (1 + g)

    # ── Implied company valuation ────────────────────────────────────────
    @row(over=[time, scenarios])
    def valuation(self, t, scenario):
        """Implied company valuation ($M) = ARR × exit multiple."""
        return self.arr(t, scenario) * self.exit_multiple[scenario]

    # ── Your stake value ─────────────────────────────────────────────────
    @row(over=[time, scenarios])
    def stake_value(self, t, scenario):
        """Your stake value ($) = investment × (valuation / entry_valuation)."""
        return self.investment_usd * (self.valuation(t, scenario) / self.entry_valuation)

    # ── Return multiple (MOIC) ───────────────────────────────────────────
    @row(over=[time, scenarios])
    def moic(self, t, scenario):
        """Money-on-invested-capital multiple."""
        return self.stake_value(t, scenario) / self.investment_usd
