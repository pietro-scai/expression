---
name: small-step-iteration
description: One change, one run, one diff, one commit. Always.
---

The iteration loop is **edit → `sweet run` → `sweet diff` → `sweet test` →
commit**. Never skip a step.

- One row changed at a time. Multi-row rewrites without an in-between solve
  hide which change broke what.
- After every code edit, call `run_model` with `subcommand="run"`. If it
  fails, fix it before doing anything else.
- Then call `run_model` with `subcommand="diff"` and **read the result to
  the user**. Don't accept silently — drift might be intentional, but the
  user has to confirm.
- If tests exist, call `run_model` with `subcommand="test"`. They must be
  green before you propose the next change.

Why: `model` is engineered around a deterministic, testable solve. Skipping
diff/test bypasses the whole point.
