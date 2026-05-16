"""Tests for the household-budget multi-model example."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from budget_model import BudgetModel
from salary_model import SalaryModel


# ── SalaryModel ──────────────────────────────────────────────────────────────

def test_salary_solves():
    m = SalaryModel()
    m.solve()


def test_salary_base_year():
    m = SalaryModel()
    m.solve()
    # gross_salary[2025] == base_salary
    assert m.gross_salary(2025) == pytest.approx(55_000.0)


def test_salary_raise_compounds():
    m = SalaryModel()
    m.solve()
    expected = 55_000.0 * (1.03 ** 5)
    assert m.gross_salary(2030) == pytest.approx(expected, rel=1e-9)


def test_net_income_less_than_gross():
    m = SalaryModel()
    m.solve()
    for t in m.time:
        assert m.net_income(t) < m.gross_income(t)


def test_net_income_positive():
    m = SalaryModel()
    m.solve()
    for t in m.time:
        assert m.net_income(t) > 0


def test_tax_equals_rate_times_gross():
    m = SalaryModel()
    m.solve()
    for t in m.time:
        assert m.tax(t) == pytest.approx(m.gross_income(t) * m.tax_rate, rel=1e-9)


# ── BudgetModel (via depends) ────────────────────────────────────────────────

def test_budget_solves():
    m = BudgetModel()
    m.solve()


def test_net_income_flows_from_salary():
    salary = SalaryModel()
    salary.solve()
    budget = BudgetModel()
    budget.solve()
    for t in salary.time:
        assert budget.salary.net_income(t) == pytest.approx(salary.net_income(t), rel=1e-9)


def test_surplus_positive_base_case():
    m = BudgetModel()
    m.solve()
    for t in m.time:
        assert m.surplus(t) > 0, f"surplus went negative in {t}"


def test_savings_cumulative_grows():
    m = BudgetModel()
    m.solve()
    prev = 0.0
    for t in m.time:
        assert m.savings_cumulative(t) > prev
        prev = m.savings_cumulative(t)


def test_total_outflows_equals_expenses_plus_savings():
    m = BudgetModel()
    m.solve()
    for t in m.time:
        assert m.total_outflows(t) == pytest.approx(
            m.fixed_expenses(t) + m.savings_contribution(t), rel=1e-9
        )


def test_housing_compounds():
    m = BudgetModel()
    m.solve()
    expected = 12_000.0 * (1.03 ** 5)
    assert m.housing(2030) == pytest.approx(expected, rel=1e-9)


def test_surplus_formula():
    m = BudgetModel()
    m.solve()
    for t in m.time:
        assert m.surplus(t) == pytest.approx(
            m.salary.net_income(t) - m.total_outflows(t), rel=1e-9
        )
