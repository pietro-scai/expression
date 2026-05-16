# BudgetModel

## Purpose
Annual household budget tracking expenses, savings, and discretionary surplus
from 2025–2030. Pulls net income from `SalaryModel` via `depends()`.

## File structure

```
household-budget/
  salary_model.py   ← SalaryModel (standalone, income only)
  budget_model.py   ← BudgetModel (depends on SalaryModel)
  household.py      ← sweet entry point (imports BudgetModel only)
```

Run: `sweet run --model household.py`  
Salary only: `sweet run --model salary_model.py`

## Inputs (globals)

| Name | Default | Description |
|---|---|---|
| `rent` | 12 000 € | Annual rent (1 000 €/month) |
| `rent_increase` | 3 % | Annual rent increase |
| `food` | 7 200 € | Food and groceries |
| `transport` | 2 400 € | Public transit + occasional car |
| `utilities` | 2 000 € | Electricity, gas, water, internet |
| `subscriptions` | 1 200 € | Subscriptions and misc |
| `savings_rate` | 15 % | Savings as fraction of net income |

## Outputs

| Row | Description |
|---|---|
| `housing[year]` | Rent compounded by `rent_increase` |
| `fixed_expenses[year]` | Sum of all recurring costs |
| `savings_contribution[year]` | `net_income × savings_rate` |
| `total_outflows[year]` | `fixed_expenses + savings_contribution` |
| `surplus[year]` | Discretionary cash: `net_income − total_outflows` |
| `savings_cumulative[year]` | Running total of savings contributions |

## Base-case headline (2025)

| Item | Amount |
|---|---|
| Net income | ~39 370 € |
| Fixed expenses | ~24 800 € |
| Savings (15 %) | ~5 906 € |
| Surplus | ~8 664 € |

## Scenarios

- `sweet overrides add savings_rate=0.20` — more aggressive savings
- `sweet overrides add rent=15000` — rent increase (moving to larger place)
- `sweet overrides add rent_increase=0.05` — hot rental market
- `sweet overrides add subscriptions=2400` — lifestyle creep

## Overrides
None.
