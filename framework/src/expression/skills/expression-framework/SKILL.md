---
name: expression-framework
description: Foundational reference for the `expression` CLI — discipline rules, workspace layout, CLI surface, exit codes, and pointers to the spec. Load this whenever the user is working in a `expression` workspace.
---

This is the framework's operator manual. It applies whenever the user is
iterating on a `expression` workspace — whether they triggered a slash command,
asked you to make a change, or just started a session in a directory that
contains `expression.py`.

## 1. Discipline (the non-negotiables)

These rules exist because the framework's value is **fast iteration with no
silent corruption**. Skip them and the loop falls apart.

- **One small change, then run.** Make a single edit, run `expression run`, look
  at the diff. Don't batch edits. If you're tempted to, stop and ship the
  first one alone first.
- **No hardcoded one-off values in formulas.** If the user says "use 0.05
  for churn this time", record it as an override (`expression overrides add`),
  do not edit the formula. Overrides are reversible; edited formulas are
  not.
- **Run after every code change.** No "this should work" — run `expression run`
  and (if `tests/` exists) `expression test`. Don't declare success without a
  green run.
- **One question at a time.** If you need information, ask for one thing.
  Three questions in one message confuses the user and the conversation
  state.
- **Reference cells in backticks.** Write `budget[2024]`, not "budget 2024"
  or "the 2024 budget cell". The doc-sync tool grepps for backticked cell
  references; consistency keeps `expression.md` in sync with the code.

## 2. Workspace layout

A `expression` workspace looks like:

```
my-expression/
  expression.py           # the DAG: one or more Model classes, rows, scalars, globs, time axis
  expression.md           # human-readable spec — paired with expression.py
  overrides.toml     # optional one-off values applied at solve time
  inputs/            # raw data files the model loads
  outputs/
    result.json      # last solve's serialized cells ({"models": [...]} shape)
    model.json       # model definition / DAG / mermaid (expression describe)
    snapshot.json    # the accepted snapshot for diffing (after `expression snapshot accept`)
  tests/             # pytest-discovered tests
  .expression/
    trace/           # per-session trace events (jsonl)
```

`expression.py` can contain **one or more `Model` subclasses**. `expression run` discovers all of
them, builds a dependency graph from their `depends()` declarations, and solves them in
topological order — no entry-point designation needed.

Most operations key off `expression.py` in the cwd. If the user is in a
subdirectory or has a non-default name, pass `--model path/to/expression.py`.

## 2.1 Modeling guardrails

- **Use `@row(over=[...])` for every multi-dimensional row.** If a row
  function has extra axis arguments such as `(self, t, company)`, bare
  `@row` is wrong: the solver will call it with only `t`. Declare the axes
  explicitly and keep the order in `over=` identical to the function
  signature:

  ```python
  companies = dim(["Co1", "Co2"])
  time = periods(2025, 2030)

  @row(over=[time, companies])
  def drawdown(self, t, company):
      ...
  ```

- **Do not rely on optional heavy dependencies unless installed.** The
  default framework environment includes the core dependencies, not packages
  like SciPy. Prefer small stdlib helpers for IRR/root-finding examples, or
  install and record the dependency before using it in model code.

## 3. CLI surface

| Command | What it does |
|---|---|
| `expression init <name>` | Scaffold a new workspace at `./<name>/` with `expression.py`, `expression.md`, `inputs/`, `outputs/`, `tests/`. |
| `expression run` | Discover all Model classes in `expression.py`, solve in DAG order, write `outputs/result.json`. **Use this constantly.** |
| `expression show <row>[<period>]` | Print one cell or whole row — searches all models. Quote brackets: `expression show 'budget[2024]'`. |
| `expression show ModelName.row[period]` | Qualified show: restrict to a specific model class. |
| `expression print` | Pretty-print all solved models as tables (separator between each). |
| `expression explain <row\|scalar>` | Show the desugared form + declared dependencies. |
| `expression describe` | Export all model definitions (DAG, source, mermaid) to `outputs/model.json`. |
| `expression diff` | Compare current solve to `.model/snapshot.json`. Exits non-zero on drift. |
| `expression snapshot accept` | Pin the current solve as the new committed snapshot. |
| `expression overrides add <target> <value>` | Record a one-off override in `overrides.toml`. |
| `expression overrides add … --model-name X` | Scope the override to model class `X` only. |
| `expression overrides list / rm / clear` | Inspect / remove overrides. |
| `expression export` | Round-trip the model out to `.xlsx`. Verifies the round-trip if `formulas` is installed. |
| `expression import <file.xlsx>` | Bring an Excel workbook into a `expression` workspace as a DAG. |
| `expression doc sync` | Report drift between `expression.py` (cells declared) and `expression.md` (cells mentioned). |
| `expression test` | Run pytest under `tests/` against the solved model. |

### Common patterns

- **After any code edit:** `expression run` (and `expression test` if tests exist).
- **Tweak something briefly:** `model overrides add row[t]=value` →
  `expression run` → review → `model overrides rm row[t]` (or `clear`).
- **Compare two states:** `expression snapshot accept` (baseline) → make change
  → `expression run` → `expression diff`.
- **Investigate a value:** `expression show 'cell[period]'` →
  `expression explain 'cell[period]'`.

## 4. Exit codes & error patterns

- Exit `0` — success.
- Exit `1` — either an error (missing file, model failed to solve, unknown
  cell, override referencing a cell that doesn't exist) **or** a non-empty
  `expression diff` / `expression doc sync` (drift is treated as failure for CI).
- Errors that start with `✗` are user-facing; they include enough context
  to point at the offending file/line. Surface them verbatim — don't
  paraphrase.
- A common `ModelError` shape: `cycle in DAG: budget → cogs → budget`.
  When you see one, run `expression explain` on the cells in the cycle.

## 5. Where to read more

Two long-form references travel with this skill — read them when you need
authoritative answers:

- `references/SPECIFICATION.md` — the formal spec for the framework
  (data model, semantics, formula language, override semantics, doc sync,
  Excel round-trip rules).
- `references/DOCS.md` — the user-facing tutorial (worked examples,
  end-to-end walkthroughs, FAQ).

These are the source of truth. If a skill seems to contradict them, the
spec wins — open an issue rather than papering over it.

## 6. Multi-model workspaces and `depends()`

A `expression.py` can contain **any number of `Model` subclasses**. `expression run`
discovers all of them, resolves their dependency order from `depends()`
declarations, and solves them without needing an entry point.

### 6.1 Same-file multi-model (preferred for tightly coupled layers)

```python
# expression.py
class SalaryModel(Model):
    time        = periods(2025, 2030)
    base_salary = glob(55_000.0)

    @row
    def gross(self, t): ...

class BudgetModel(Model):
    time   = periods(2025, 2030)
    salary = depends(SalaryModel)   # wire the data bridge

    @row
    def savings(self, t):
        return self.salary.gross(t) * 0.15
```

`expression run` output:
```
✓ Discovered 2 models: SalaryModel -> BudgetModel
  ✓ Solved SalaryModel (1 row, 6 cells)
  ✓ Solved BudgetModel (1 row, 6 cells)
✓ Wrote outputs/result.json
```

### 6.2 Multi-file (preferred for shared/reusable upstreams)

```
workspace/
  cost_model.py       # class CostModel(Model): ...
  pnl/expression.py        # imports and connects
```

```python
# pnl/expression.py
from cost_model import CostModel

class PnLModel(Model):
    time = periods(2024, 2028)
    cost = depends(CostModel)

    @row
    def margin(self, t):
        return self.revenue(t) - self.cost.opex(t)
```

Run with: `expression run` (from `pnl/`). The upstream `CostModel` is resolved
lazily — no separate `expression run` needed.

### 6.3 Rules for `depends()`

- The full dependency graph must be a DAG. A cycle raises `ModelError`
  with the cycle path at class-definition time (within a class) or at
  `expression run` time (across models in the same file).
- Each upstream model is instantiated and solved before any downstream
  row can call it.
- Access upstream rows as `self.<dep>.<row>(t)`.

### 6.4 Qualifying `show` for multi-model

```bash
expression show 'gross[2025]'              # searches all models
expression show 'SalaryModel.gross[2025]'  # scoped to one model
```

### 6.5 Scoping overrides by model

```bash
expression overrides add base_salary 60000 --model-name SalaryModel
```

Without `--model-name`, the override applies to every model that has a
row or glob with that name.

## 7. What to do when you get stuck

- The model failed to solve → read the error; run `expression explain` on any
  cell mentioned; check `overrides.toml` for stale entries.
- Diff shows unexpected churn → revert to the last commit, re-run, then
  re-apply changes one at a time so you isolate which edit caused which
  cell to move.
- Excel round-trip lost a formula → check `excel-fidelity` skill; some
  Excel-specific functions don't have a clean DAG mapping.
- The user keeps asking about an Excel concept → check `import-excel` and
  `excel-fidelity` skills; the conventions are spelled out there.
