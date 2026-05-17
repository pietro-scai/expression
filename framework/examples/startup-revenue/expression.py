from expression import Model, periods, glob, row


class StartupRevenue(Model):
    """Startup revenue projection with 20% monthly compounding growth (2025–2030)."""

    time = periods(2025, 2030)

    seed_revenue   = glob(120,  doc="Starting annual revenue in 2025 ($K)")
    monthly_growth = glob(0.20, doc="Monthly revenue growth rate (0.20 = 20%)")

    @row
    def annual_growth_rate():
        """Effective annual growth rate from monthly compounding."""
        annual_growth_rate[n] = (1 + monthly_growth) ** 12 - 1

    @row
    def revenue():
        """Annual revenue ($K), compounding at the effective annual rate."""
        revenue[first] = seed_revenue
        revenue[n]     = revenue[n-1] * (1 + annual_growth_rate[n])

    @row
    def yoy_growth_pct():
        """Year-over-year revenue growth (%)."""
        yoy_growth_pct[first] = 0
        yoy_growth_pct[n]     = (revenue[n] / revenue[n-1] - 1) * 100

    @row
    def cumulative_revenue():
        """Cumulative revenue since 2025 ($K)."""
        cumulative_revenue[first] = revenue[first]
        cumulative_revenue[n]     = cumulative_revenue[n-1] + revenue[n]
