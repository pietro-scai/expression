"""
Salary Model
============
Tracks a household's income sources and net take-home pay from 2025 to 2030.

Run standalone: sweet run --model salary_model.py
"""

from sweet import Model, glob, periods, row


class SalaryModel(Model):
    time = periods(2025, 2030)

    # ── Income inputs ────────────────────────────────────────────────────────
    base_salary    = glob(55_000.0, doc="Annual gross base salary (€)")
    annual_raise   = glob(0.03,     doc="Annual raise rate")
    bonus_rate     = glob(0.10,     doc="Bonus as fraction of gross salary")
    side_income    = glob(3_000.0,  doc="Annual side income — freelance, consulting (€)")
    tax_rate       = glob(0.38,     doc="Effective income tax + social contributions rate")

    # ── Rows ─────────────────────────────────────────────────────────────────

    @row
    def gross_salary(self, t):
        if t == self.time.first:
            return self.base_salary
        return self.gross_salary(t - 1) * (1 + self.annual_raise)

    @row
    def bonus(self, t):
        return self.gross_salary(t) * self.bonus_rate

    @row
    def gross_income(self, t):
        return self.gross_salary(t) + self.bonus(t) + self.side_income

    @row
    def tax(self, t):
        return self.gross_income(t) * self.tax_rate

    @row
    def net_income(self, t):
        return self.gross_income(t) - self.tax(t)
