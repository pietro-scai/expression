"""
Budget Model
============
Tracks a household's expenses, savings, and monthly surplus against net income
pulled from SalaryModel via depends().

Not meant to be run directly with sweet — use household.py as the entry point.
"""

from salary_model import SalaryModel

from sweet import Model, depends, glob, periods, row


class BudgetModel(Model):
    time = periods(2025, 2030)

    salary = depends(SalaryModel)

    # ── Expense inputs ───────────────────────────────────────────────────────
    rent           = glob(12_000.0, doc="Annual rent (€/yr — 1 000/month)")
    rent_increase  = glob(0.03,     doc="Annual rent increase rate")
    food           = glob(7_200.0,  doc="Annual food and groceries (€)")
    transport      = glob(2_400.0,  doc="Annual transport — public transit + occasional car (€)")
    utilities      = glob(2_000.0,  doc="Annual utilities — electricity, gas, water, internet (€)")
    subscriptions  = glob(1_200.0,  doc="Annual subscriptions and miscellaneous (€)")
    savings_rate   = glob(0.15,     doc="Savings as fraction of net income")

    # ── Rows ─────────────────────────────────────────────────────────────────

    @row
    def housing(self, t):
        if t == self.time.first:
            return self.rent
        return self.housing(t - 1) * (1 + self.rent_increase)

    @row
    def fixed_expenses(self, t):
        return (
            self.housing(t)
            + self.food
            + self.transport
            + self.utilities
            + self.subscriptions
        )

    @row
    def savings_contribution(self, t):
        return self.salary.net_income(t) * self.savings_rate

    @row
    def total_outflows(self, t):
        return self.fixed_expenses(t) + self.savings_contribution(t)

    @row
    def surplus(self, t):
        """Discretionary cash left after expenses and savings."""
        return self.salary.net_income(t) - self.total_outflows(t)

    @row
    def savings_cumulative(self, t):
        if t == self.time.first:
            return self.savings_contribution(t)
        return self.savings_cumulative(t - 1) + self.savings_contribution(t)
