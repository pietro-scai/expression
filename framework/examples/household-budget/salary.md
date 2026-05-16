# SalaryModel

## Purpose
Annual household income from employment, bonus, and side work — net of taxes.
Covers 2025–2030. Used as an upstream dependency by `BudgetModel`.

## Inputs (globals)

| Name | Default | Description |
|---|---|---|
| `base_salary` | 55 000 € | Annual gross base salary |
| `annual_raise` | 3 % | Annual raise rate |
| `bonus_rate` | 10 % | Bonus as fraction of gross salary |
| `side_income` | 3 000 € | Freelance / consulting income per year |
| `tax_rate` | 38 % | Effective income tax + social contributions |

## Outputs

| Row | Description |
|---|---|
| `gross_salary[year]` | Base salary compounded by `annual_raise` |
| `bonus[year]` | `gross_salary × bonus_rate` |
| `gross_income[year]` | `gross_salary + bonus + side_income` |
| `tax[year]` | `gross_income × tax_rate` |
| `net_income[year]` | Take-home: `gross_income − tax` |

## Scenarios

- `sweet overrides add gross_salary[2027]=65000` — promotion in 2027
- `sweet overrides add bonus_rate=0.20` — doubled bonus scheme
- `sweet overrides add tax_rate=0.30` — move to lower-tax jurisdiction
- `sweet overrides add side_income=8000` — side project takes off
