from sweet import Model, periods, glob, row, dim


class BudgetModel(Model):
    """Simple annual budget model tracking income, expenses, and net balance."""

    time = periods(2025, 2030)

    # --- Income assumptions ---
    base_salary = glob(120_000, doc="Base salary income ($/yr)")
    salary_growth = glob(0.04, doc="Annual salary growth rate")
    other_income = glob(12_000, doc="Other income per year (freelance, dividends, etc.)")

    # --- Expense assumptions ---
    housing = glob(24_000, doc="Annual housing cost (rent/mortgage)")
    food = glob(7_200, doc="Annual food & groceries")
    transport = glob(4_800, doc="Annual transport cost")
    utilities = glob(2_400, doc="Annual utilities")
    entertainment = glob(3_600, doc="Annual entertainment & subscriptions")
    misc_expenses = glob(3_000, doc="Miscellaneous expenses")
    expense_growth = glob(0.03, doc="Annual expense inflation rate")

    # --- Rows ---

    @row
    def salary():
        """Salary income, growing each year ($)."""
        salary[first] = base_salary
        salary[n] = salary[n - 1] * (1 + salary_growth)

    @row
    def total_income():
        """Total income = salary + other income ($)."""
        total_income[n] = salary[n] + other_income

    @row
    def fixed_expenses():
        """Fixed annual expenses, inflation-adjusted ($)."""
        fixed_expenses[first] = (
            housing + food + transport + utilities + entertainment + misc_expenses
        )
        fixed_expenses[n] = fixed_expenses[n - 1] * (1 + expense_growth)

    @row
    def total_expenses():
        """Total expenses ($)."""
        total_expenses[n] = fixed_expenses[n]

    @row
    def net_budget():
        """Net budget surplus / (deficit) = income - expenses ($)."""
        net_budget[n] = total_income[n] - total_expenses[n]

    @row
    def savings_rate():
        """Savings rate = net budget / total income (%)."""
        savings_rate[n] = net_budget[n] / total_income[n]

    @row
    def cumulative_savings():
        """Cumulative savings over the planning horizon ($)."""
        cumulative_savings[first] = net_budget[first]
        cumulative_savings[n] = cumulative_savings[n - 1] + net_budget[n]
