---
name: bottom-up-modeling
description: Build models from the leaves upward. Don't start with the answer.
---

When the user describes a new model, do **not** start by writing the row that
answers their question (revenue forecast, NPV, etc.). Start at the leaves:

1. List the **inputs** the user has or needs to estimate (raw numbers,
   datasets, named ranges).
2. List the **assumptions** (growth rates, discount rates, allocations).
3. Sketch the **dependency tree** before writing any formulas. Confirm it
   with the user.
4. Implement leaves first (`glob(...)` + simple `@row` rows). Run after
   each row.
5. Compose upward toward the user's headline number.

When a row varies by a categorical axis, define the `dim(...)` first and use
`@row(over=[...])`; a bare `@row` with extra function arguments will fail at
solve time. Prefer stdlib math/helpers in formulas unless the workspace has
explicitly installed an optional dependency such as SciPy.

Reasoning: bottom-up forces the user to surface every assumption explicitly.
A top-down sketch tends to leave hidden plug numbers in formulas — exactly
the thing `model` exists to eliminate.
