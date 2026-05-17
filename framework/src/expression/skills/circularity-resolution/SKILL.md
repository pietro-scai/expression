---
name: circularity-resolution
description: When solve() raises CircularReferenceError, walk the user through breaking it.
---

When `expression run` reports a `Circular dependency between rows: A -> B -> A`,
do not "fix" by guessing. Walk the user through one of three breaks:

1. **Lag.** Replace `A[n] = f(B[n])` with `A[n] = f(B[n-1])` if the timing
   makes sense.
2. **Simplification.** One side of the cycle can often be expressed without
   the other if the user clarifies the business meaning. Ask.
3. **Split.** Some Excel models encode an iterative goal-seek as circular.
   Replace with a closed-form or an explicit `xl.solve_for(...)`.

Always ask the user which break is right. Never silently rewrite formulas to
remove a cycle — the cycle usually means a real modeling decision was
deferred.
