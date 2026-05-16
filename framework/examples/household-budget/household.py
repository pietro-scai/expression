"""
Household — entry point for sweet.

Imports only BudgetModel (which internally depends on SalaryModel).
sweet's CLI sees exactly one Model subclass here, so Phase 0 is satisfied.

Run: sweet run --model household.py
"""

from budget_model import BudgetModel

__all__ = ["BudgetModel"]
