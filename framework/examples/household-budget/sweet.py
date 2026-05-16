from sweet import Model, periods, glob, row, dim, depends


class SalaryModel(Model):
    """Detailed salary breakdown feeding into the household budget."""

    time = periods(2025, 2030)

    base_salary     = glob(100000, doc="Starting base salary ($)")
    salary_increase = glob(0.03,   doc="Annual base salary increase rate")
    bonus_rate      = glob(0.10,   doc="Annual bonus as a fraction of base salary")
    extra_bonus     = glob(5000,   doc="Extra bonus paid every two years ($)")

    @row
    def base(self, t):
        """Base salary after annual increases ($)."""
        if t == self.time.first:
            return self.base_salary
        return self.base(t - 1) * (1 + self.salary_increase)

    @row
    def bonus(self, t):
        """Annual performance bonus ($)."""
        return self.base(t) * self.bonus_rate

    @row
    def extra_bonus_payment(self, t):
        """Extra bonus paid every two years — odd years from start ($)."""
        if (t - self.time.first) % 2 == 1:
            return self.extra_bonus
        return 0

    @row
    def total_compensation(self, t):
        """Total gross compensation: base + bonus + extra bonus ($)."""
        return self.base(t) + self.bonus(t) + self.extra_bonus_payment(t)


class HouseholdBudget(Model):
    """Annual household budget, driven by SalaryModel for income."""

    time = periods(2025, 2030)

    salary = depends(SalaryModel)

    # --- Expenses ---
    housing_cost      = glob(18000, doc="Annual housing cost — rent/mortgage ($)")
    groceries         = glob(7200,  doc="Annual grocery spending ($)")
    transport         = glob(5400,  doc="Annual transport cost ($)")
    utilities         = glob(2400,  doc="Annual utilities ($)")
    entertainment     = glob(3000,  doc="Annual entertainment & dining ($)")
    expense_inflation = glob(0.025, doc="Annual expense inflation rate")

    # --- Tax ---
    tax_rate          = glob(0.22,  doc="Effective income tax rate")

    @row
    def gross_income(self, t):
        """Gross household income — sourced from SalaryModel ($)."""
        return self.salary.total_compensation(t)

    @row
    def taxes(self, t):
        """Income taxes paid ($)."""
        return self.gross_income(t) * self.tax_rate

    @row
    def net_income(self, t):
        """Take-home pay after taxes ($)."""
        return self.gross_income(t) - self.taxes(t)

    @row
    def total_expenses(self, t):
        """Total annual household expenses ($)."""
        base = (self.housing_cost + self.groceries +
                self.transport + self.utilities + self.entertainment)
        if t == self.time.first:
            return base
        return self.total_expenses(t - 1) * (1 + self.expense_inflation)

    @row
    def net_savings(self, t):
        """Annual net savings ($)."""
        return self.net_income(t) - self.total_expenses(t)

    @row
    def savings_rate(self, t):
        """Savings as a share of net income (%)."""
        return self.net_savings(t) / self.net_income(t)

    @row
    def cumulative_savings(self, t):
        """Running total of savings accumulated ($)."""
        if t == self.time.first:
            return self.net_savings(t)
        return self.cumulative_savings(t - 1) + self.net_savings(t)
