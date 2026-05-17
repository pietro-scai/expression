# `expression` — User Guide

> A CLI for treating Excel-like spreadsheets as Python DAGs, with an agent loop on top so you never have to open Excel again.

This guide walks you from "empty folder" to "a model an agent can iterate on", introducing each feature only when you need it. Read top-to-bottom the first time. Skim later.

---

## Table of contents

1. [Getting started](#1-getting-started)
2. [Your first model](#2-your-first-model)
3. [Running and inspecting a model](#3-running-and-inspecting-a-model)
4. [Data in / data out](#4-data-in--data-out)
5. [Sugar — the Layer-2 DSL](#5-sugar--the-layer-2-dsl)
6. [The `xl.*` function library](#6-the-xl-function-library)
7. [Scalar rows](#7-scalar-rows)
8. [Multi-dimensional rows](#8-multi-dimensional-rows)
9. [Overrides](#9-overrides)
10. [Snapshots and `expression diff`](#10-snapshots-and-model-diff)
11. [Reconciling code and `expression.md`](#11-reconciling-code-and-modelmd)
12. [Cross-model dependencies](#12-cross-model-dependencies)
13. [Multiple models in one file](#13-multiple-models-in-one-file)
14. [Excel import / export](#14-excel-import--export)
15. [Printing](#15-printing)
16. [The agent loop](#16-the-agent-loop)
17. [Skills](#17-skills)
18. [Harnesses — Claude Code, Codex, your own](#18-harnesses--claude-code-codex-your-own)
19. [Traces and debugging the agent](#19-traces-and-debugging-the-agent)
20. [Cheatsheet](#20-cheatsheet)

---

## 1. Getting started

`expression` runs on Python 3.11+. The recommended toolchain is [`uv`](https://docs.astral.sh/uv/), but anything that installs from a `pyproject.toml` works.

### 1.1 Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
```

### 1.2 Create a project folder

```bash
mkdir my-models && cd my-models
uv init --bare        # creates pyproject.toml, no main.py
uv add expression          # if `model` is published; else add as a path/git dep
```

For local development against this repo:

```bash
uv add --editable /path/to/model           # path dependency
# or
uv add "model @ git+https://…/model.git"   # git dependency
```

Optional extras:

```bash
uv add 'expression[agent]'    # pulls anthropic SDK for `model agent`
uv add 'expression[verify]'   # pulls `formulas` for stronger Excel verification
uv add 'expression[dev]'      # pytest, ruff, pyright
```

Verify it's wired up:

```bash
uv run expression --help
```

You should see the top-level CLI: `init`, `run`, `show`, `print`, `export`, `import`, `explain`, `diff`, `snapshot`, `overrides`, `doc`, `agent`.

### 1.3 Scaffold a model

```bash
uv run expression init budget
```

This creates a folder:

```
budget/
├── expression.py        # one Model subclass, ready to edit
├── expression.md        # human-readable spec, kept in sync with code
├── inputs/         # CSV/JSON datasets your model reads
├── outputs/        # solve results land here
└── tests/          # add pytest cases (auto-discovered)
```

The starter `expression.py` ships with a working budget example so the very first `expression run` succeeds.

```bash
cd budget
uv run expression run
```

Expected output:

```
✓ DAG validated (1 row, 5 cells)
✓ Solved
  budget: [100.0, 105.0, 110.25, 115.7625, 121.55…]
✓ Wrote outputs/result.json
```

You're up.

---

## 2. Your first model

A `expression.py` is a Python file that defines one `Model` subclass. The class has three kinds of attribute:

| Attribute | Purpose | Example |
|---|---|---|
| `time = periods(start, end)` | The single period axis (inclusive). | `periods(2024, 2028)` |
| `name = glob(default, doc=…)` | A named global parameter. | `growth_rate = glob(0.05)` |
| `@row` / `@scalar` | A function that produces values. | `def budget(self, t): …` |

A minimal Layer-1 (pure-Python) model:

```python
from expression import Model, glob, periods, row

class Budget(Model):
    time        = periods(2024, 2028)
    seed        = glob(100, doc="Starting budget in $K")
    growth_rate = glob(0.05, doc="Annual growth rate")

    @row
    def budget(self, t):
        if t == self.time.first:
            return self.seed
        return self.budget(t - 1) * (1 + self.growth_rate)
```

Three things to know:

- **Rows are functions.** `budget(self, t)` is called once per period. The framework caches per `(row, t)` so `self.budget(t-1)` returns the already-computed value.
- **Globals are descriptors.** `self.growth_rate` returns the *value*, not a wrapper. Setting `model.growth_rate = 0.07` overrides it on this instance.
- **The DAG is implicit.** Whatever cells you reference inside a row body become its dependencies. Cycles are detected at solve time and raise `CircularReferenceError`.

---

## 3. Running and inspecting a model

The four core commands.

### 3.1 `expression run`

Topologically solves the DAG, writes `outputs/result.json`, and echoes each row:

```bash
$ expression run
✓ DAG validated (1 row, 5 cells)
✓ Solved
  budget: [100.0, 105.0, 110.25, 115.76, 121.55]
✓ Wrote outputs/result.json
```

Flags:

- `--mode=eager` (default; only mode shipped today). `lazy` and `reactive` are reserved for future versions.
- `--model PATH` — point at a different `expression.py` (defaults to `./expression.py`).

### 3.2 `expression show`

Print one cell or one whole row:

```bash
$ expression show budget
budget[2024] = 100.0
budget[2025] = 105.0
…

$ expression show 'budget[2026]'
budget[2026] = 110.25
```

Quote the bracketed form — most shells try to glob `[…]`.

### 3.3 `expression explain`

Show the desugared (Layer-1) form of a row plus its declared dependencies:

```bash
$ expression explain budget
# budget (row)
# depends on: growth_rate, seed

@row
def budget(self, t):
    if t == self.time.first:
        return self.seed
    return self.budget(t - 1) * (1 + self.growth_rate)
```

Equivalent for a `@scalar`. This is the inspectability contract for Layer-2 sugar (see §5): whatever your sugared body becomes at class-definition time, `expression explain` will print.

### 3.4 `expression print`

Render the solved model as a column-aligned table or CSV:

```bash
$ expression print
        2024    2025    2026    2027    2028
budget   100   105.0  110.25  115.76  121.55

$ expression print --format csv > snapshot.csv
```

`-f`/`--format` accepts `table` (default) or `csv`.

---

## 4. Data in / data out

There are five ways data flows in and out of a `model`:

### 4.1 Globals (`glob`)

A scalar input with a default and an optional doc string.

```python
discount_rate = glob(0.10, doc="Annual discount rate")
```

Read as `self.discount_rate`. Override at the instance level by assigning to it (`model.discount_rate = 0.12`) or via `overrides.toml` (§9).

### 4.2 Periods (`periods`)

The integer-period axis. Phase 0/1 expects exactly one `periods(...)` per model.

```python
time = periods(2024, 2028)   # inclusive: [2024, 2025, 2026, 2027, 2028]
self.time.first              # 2024
self.time.last               # 2028
list(self.time)              # [2024, …, 2028]
```

### 4.3 Dimensions (`dim`) and matrices (`matrix`)

For multi-dimensional data:

```python
products = dim(['A', 'B', 'C'])
regions  = dim(['EU', 'US', 'APAC'])

base_price = matrix(products, regions, default=10.0)
# or, with per-key defaults:
base_price = matrix(products, default={'A': 10, 'B': 25})
```

Read/write with subscripts: `self.base_price[p, r]` returns the override (if any) or the default; `self.base_price[p, r] = 12.5` records a per-instance override.

### 4.4 CSV datasets (`dataset.csv`)

```python
from expression import Model, dataset, periods, row

class Forecast(Model):
    time       = periods(2024, 2028)
    historical = dataset.csv("inputs/historical.csv", index="date")

    @row
    def forecast(self, t):
        if t == self.time.first:
            return self.historical.last("revenue")
        return self.forecast(t - 1) * 1.05
```

The CSV is loaded lazily on first access; values are coerced to `int`/`float`/`str`. The `Dataset` API:

| Method | Use |
|---|---|
| `ds.last(col)` | Last row's value in `col` |
| `ds.first(col)` | First row's value |
| `ds.lookup(key, col)` | Row whose index matches `key`, then `col` |
| `ds.column(col)` | All values in `col` (in row order) |
| `ds.rows`, `ds.columns` | Raw `list[dict]`, column names |

### 4.5 Output: `dataset.from_row`

Turn any solved row back into a `Dataset` for downstream consumers:

```python
from expression import dataset

projections = dataset.from_row(model, "forecast", columns=["year", "revenue"])
```

The shape is `[{period_col: t, value_col: …}, …]`. Useful when chaining models or writing custom exporters.

### 4.6 What `expression run` writes

Every solve writes `outputs/result.json`. The shape mirrors the model — model metadata, axes, inputs (globs), one `tables` entry per `@row` (with docstring, columns, and per-period results), and `scalars`:

```json
{
  "model": {
    "name": "Budget",
    "doc": "…class docstring…",
    "axes": {"time": {"kind": "periods", "values": [2024, 2025, …]}}
  },
  "inputs": {
    "seed":        {"value": 100,  "default": 100,  "type": "int",   "doc": "Starting budget"},
    "growth_rate": {"value": 0.05, "default": 0.05, "type": "float", "doc": "Annual growth rate"}
  },
  "tables": [
    {
      "name": "budget",
      "kind": "row",
      "doc": "Yearly budget projection.",
      "depends_on": ["seed", "growth_rate"],
      "columns": [{"kind": "periods", "values": [2024, 2025, …]}],
      "results": {"2024": 100.0, "2025": 105.0, …}
    }
  ],
  "scalars": [
    {"name": "npv", "kind": "scalar", "doc": "…", "depends_on": [...], "type": "float", "value": 1234.5}
  ]
}
```

`depends_on` is populated for Layer-2 rows (the AST rewriter records explicit deps); Layer-1 rows leave it as `[]`. The committed snapshot for `expression diff` (§10) lives separately at `.model/snapshot.json` and keeps a flat `{"row[period]": value}` shape for cell-level diffing.

### 4.7 What `expression describe` writes

`expression describe` writes `outputs/model.json` — the model's *definition*, not its solved values. It's the right input to feed an LLM, render an architecture diagram, or diff model structure across branches.

```json
{
  "models": [
    {
      "name": "Budget",
      "doc": "…class docstring…",
      "axes": {"time": {"kind": "periods", "values": [2024, …]}},
      "globals": {
        "seed":        {"default": 100,  "type": "int",   "doc": "…"},
        "growth_rate": {"default": 0.05, "type": "float", "doc": "…"}
      },
      "rows": [
        {
          "name": "budget",
          "kind": "row",
          "doc": "Yearly budget projection.",
          "depends_on": ["growth_rate", "seed"],
          "columns": [{"kind": "periods", "values": [2024, …]}],
          "source": "@row\ndef budget(self, t):\n    …"
        }
      ],
      "scalars": [],
      "dag": {
        "nodes": [{"name": "seed", "kind": "glob"}, …],
        "edges": [{"from": "seed", "to": "budget"}, …]
      },
      "mermaid": "graph TD\n    seed([seed])\n    budget[budget]\n    seed --> budget"
    }
  ],
  "documentation": "…contents of expression.md if present…"
}
```

The DAG includes globals as source nodes (stadium `([…])` in mermaid) so the diagram captures the full data flow. Dependencies are extracted by AST scan of each row's source — globals counted, self-references excluded.

---

## 5. Sugar — the Layer-2 DSL

Layer-1 (`def budget(self, t): …`) always works. Layer-2 is an AST rewrite of `@row` / `@scalar` bodies that gives you Excel-like notation.

The trigger is simple: **a row function with no positional arguments is treated as Layer 2.**

```python
from expression import Model, glob, periods, row

class Budget(Model):
    time        = periods(2024, 2028)
    seed        = glob(100)
    growth_rate = glob(0.05)

    @row
    def budget():
        budget[first] = seed
        budget[n]     = budget[n-1] * (1 + growth_rate)
```

What the rewriter does:

| Sugar | Layer-1 equivalent |
|---|---|
| `budget[first]` | `self.budget(self.time.first)` |
| `budget[last]` | `self.budget(self.time.last)` |
| `budget[n]`, `budget[t]` | `self.budget(t)` (current period) |
| `budget[n-1]`, `budget[n-2]` | `self.budget(t-1)`, `self.budget(t-2)` |
| `budget[2024]` | `self.budget(2024)` |
| `budget[:]` | `self.series("budget")` (full array) |
| `budget[2024:2027]` | inclusive list `[budget(2024)…budget(2027)]` |
| `growth_rate` (bare) | `self.growth_rate` |

Assignments in the body become guards on `t`: `name[first] = expr` becomes an `if t == self.time.first: return expr` branch; `name[n] = expr` becomes the default `return expr`.

### 5.1 Toggling sugar

Sugar is on by default. Disable it per class for round-tripping unfamiliar Excel:

```python
class Imported(Model, sugar=False):
    ...
```

Inside a `sugar=False` class, every row must be Layer-1 (`def name(self, t)`).

### 5.2 Inspecting the rewrite

Run `expression explain <row>` to see exactly what the rewriter produced. There is no hidden behaviour — if `explain` doesn't show what you expected, your sugar is wrong.

### 5.3 Limits (Phase 1)

- Body must be assignments only (one per branch). Tuple assignment is not supported.
- Open-ended slices like `budget[:n]` are **not** supported yet — use `xl.cumsum`/`xl.first_where` or write Layer-1.
- Slices like `budget[a:b]` are **inclusive** of `b` (Excel semantics, not Python).

When sugar gets in the way, drop to Layer-1 — it's always a one-liner away.

---

## 6. The `xl.*` function library

`xl` is a plain Python module of Excel-flavoured functions. Import it where you write expressions:

```python
from expression import Model, glob, periods, row, scalar, xl

class Investment(Model):
    time          = periods(2024, 2030)
    discount_rate = glob(0.10)

    @row
    def cash_flow():
        cash_flow[first] = -1000
        cash_flow[n]     = 200 + cash_flow[n-1] * 0.05

    @scalar
    def npv():
        return xl.npv(discount_rate, cash_flow[:])
```

### 6.1 Catalogue

| Category | Functions |
|---|---|
| Statistical | `sum`, `avg`, `min`, `max`, `stdev`, `var`, `median`, `percentile` |
| Logical | `if_`, `and_`, `or_`, `not_`, `iferror` |
| Financial | `npv`, `xnpv`, `irr`, `xirr`, `mirr`, `pmt`, `pv`, `fv`, `rate`, `nper` |
| Date | `eomonth`, `edate`, `yearfrac`, `workday` |
| Series | `cumsum`, `running_max`, `drawdown`, `first_where`, `last_where` |
| Lookup | `vlookup`, `index_match`, `xlookup` (call `.lookup` on the table) |

Notes:

- `xl.npv(rate, cash_flows)` discounts index 0 by **one** period — matches Excel `NPV`. For "investment-at-time-0", write `cf[0] + xl.npv(rate, cf[1:])`.
- `xl.irr` does Newton's method then bisection fallback.
- `xl.first_where(values, pred)` returns a 0-based index (or `None`). Map to a period via `model.time.values[i]` if you need the label.
- `xl.iferror(thunk, fallback)` takes a callable so the expression isn't evaluated twice.

### 6.2 Registering custom functions

```python
from expression import xl

@xl.register
def sharpe(returns, risk_free=0.02):
    excess = [r - risk_free for r in returns]
    return xl.avg(excess) / xl.stdev(excess)

# usable anywhere:
@scalar
def my_sharpe():
    return xl.sharpe(returns[:])
```

`@xl.register` (also exported as `model.register`) injects the function into the `xl` namespace.

---

## 7. Scalar rows

Some quantities aggregate over a whole row — IRR, NPV, totals. Use `@scalar`:

```python
from expression import Model, scalar, row, glob, periods, xl

class Deal(Model):
    time          = periods(2024, 2030)
    discount_rate = glob(0.12)

    @row
    def cash_flow():
        cash_flow[first] = -5_000_000
        cash_flow[n]     = 1_000_000

    @scalar
    def npv():
        return xl.npv(discount_rate, cash_flow[:])

    @scalar
    def irr():
        return xl.irr(cash_flow[:])
```

Scalars are first-class DAG nodes. They:

- Are accessed as `self.npv` (a value, not a callable).
- Show up in `model print` as `name = value` lines under the rows.
- Round-trip to Excel as a single named cell.
- Can be overridden via `overrides.toml` (no `period`).

Layer-1 form is just `def npv(self): return …` — sugar is detected the same way (no positional args = Layer 2).

---

## 8. Multi-dimensional rows

When a row varies over more than just `time`, declare its axes with `@row(over=…)`:

```python
class Pricing(Model):
    products = dim(['A', 'B', 'C'])
    regions  = dim(['EU', 'US', 'APAC'])
    time     = periods(2024, 2026)

    base_price = matrix(products, regions, default=10.0)
    tax_rate   = matrix(regions, time, default=0.2)

    @row(over=[products, regions, time])
    def revenue(self, p, r, t):
        return self.base_price[p, r] * (1 + self.tax_rate[r, t]) * units_sold[p, r, t]
```

The framework iterates the cartesian product of the declared axes and caches per `(row_name, *idx)`. Order of axes in `over=` is the order of the function's positional arguments.

Bare `@row` is only for one-dimensional time rows. If the function signature
has any extra axis argument, for example `def drawdown(self, t, company)`, it
must use `@row(over=[time, companies])`; otherwise the solver calls it with
only `t` and the model fails before writing `outputs/result.json`.

For multi-dim cells, `model.cell("revenue", ("A", "EU", 2024))` (tuple) returns the value.

---

## 9. Overrides

Hardcoded one-off adjustments are recorded as data, never edited into formulas.

`overrides.toml` lives next to `expression.py`:

```toml
[[override]]
row = "budget"
period = 2025
value = 150
reason = "Board adjustment Q4 2024"
author = "pietro"

[[override]]
glob = "growth_rate"
value = 0.07
reason = "Updated forecast"
```

`expression run` applies overrides *before* solving:

- **Row overrides** are pre-populated into the cell cache; downstream cells see them naturally.
- **Glob overrides** set the instance attribute via the descriptor.
- **Scalar overrides** target a `@scalar` row — omit `period`.

### 9.1 CLI

```bash
expression overrides add budget 2025 150 --reason "Board adjustment"
expression overrides add growth_rate 0.07 --glob --reason "Updated forecast"
expression overrides list
expression overrides rm budget 2025
expression overrides clear --yes
```

The `value` argument is parsed as JSON when possible (so `0.05`, `true`, `"text"`, `[1,2,3]` all work); otherwise treated as a string.

The `expression run` echo line shows whether overrides were applied: `✓ Solved with 1 override`.

---

## 10. Snapshots and `expression diff`

`outputs/result.json` is rewritten on every run — that's the *latest* solve. The *committed* snapshot lives at `.model/snapshot.json` and only updates when you accept it.

```bash
$ expression snapshot accept
✓ Wrote snapshot to .model/snapshot.json
```

After making changes, see what moved:

```bash
$ expression run
$ expression diff
# changed (1)
  ~ budget[2025]: 105.0 → 110.0
```

Exit code is non-zero when there's a diff, so CI can gate merges. Re-`accept` once you're happy.

The diff is **exact** — solving is deterministic, and a `1e-15` drift is worth surfacing. Add a `--tol` flag if it ever causes friction.

---

## 11. Reconciling code and `expression.md`

`expression.md` is the human-readable spec. It's not auto-generated — you write it — but the framework checks for drift between what the code declares and what the markdown mentions.

Mention contract: a name in the markdown counts as "documented" if it appears inside backticks (`` `budget` ``, `` `budget[2024]` ``).

```bash
$ expression doc sync
# In code but not in expression.md (1)
  - cogs
# Mentioned in expression.md but not in code (1)
  - revenu
```

Exit code is non-zero on drift. The agent loop (§15) uses this same primitive for interactive reconciliation.

The markdown structure the framework expects (PRD §6):

```markdown
# Budget model
## Purpose            (one paragraph)
## Inputs             (globals, datasets)
## Outputs            (rows, scalars)
## Logic              (prose explanation)
## Known issues / open questions
## Overrides          (auto-listed)
## Changelog          (append-only)
```

---

## 12. Cross-model dependencies

Compose models across files with `depends`:

```python
# costs/expression.py
from expression import Model, periods, row

class Costs(Model):
    time = periods(2024, 2026)
    @row
    def total_cost(self, t): ...

# pnl/expression.py
from expression import Model, depends, periods, row
from costs.expression import Costs

class PnL(Model):
    time  = periods(2024, 2026)
    costs = depends(Costs)

    @row
    def margin(self, t):
        return self.revenue(t) - self.costs.total_cost(t)
```

`self.costs` returns a *solved* upstream instance, lazily constructed and cached on the dependent. Cycles across `depends()` chains are detected at class-definition time (raise `ModelError`).

In Layer-2 sugar, bare `costs.total_cost[n]` works — `costs` is a known model attribute, so it's prefixed with `self.` automatically.

---

## 13. Multiple models in one file

Excel workbooks have multiple sheets, each of which is its own "model layer". The expression equivalent is **multiple `Model` subclasses in the same `expression.py`** — one per logical layer. `expression run` discovers all of them automatically, resolves their dependency order, and writes a combined `outputs/result.json`.

### 13.1 When to use it

Put multiple models in one file when the layers belong to the same workspace and interact with each other. Use separate files (multi-file mode) when the upstream model is a reusable library shared by other workspaces.

| Scenario | Recommended layout |
|---|---|
| Salary layer + Budget layer in the same household model | One file, two classes |
| Shared cost-base used by many different models | Separate file + `import` + `depends()` |
| Three independent sensitivity scenarios | One file, three classes |

### 13.2 Defining multiple models

Add as many `Model` subclasses to `expression.py` as you like. Connect them with `depends()` exactly as in the multi-file case — `depends()` is still required for one model's rows to access another's solved values.

```python
# expression.py
from expression import Model, depends, glob, periods, row, scalar

class SalaryModel(Model):
    """Layer 1: gross → net salary."""
    time        = periods(2025, 2030)
    base_salary = glob(55_000.0, doc="Annual gross base salary")
    raise_rate  = glob(0.03)

    @row
    def gross(self, t):
        if t == self.time.first:
            return self.base_salary
        return self.gross(t - 1) * (1 + self.raise_rate)

    @row
    def net(self, t):
        return self.gross(t) * 0.72  # ~28% effective tax

class BudgetModel(Model):
    """Layer 2: savings and spending from net salary."""
    time           = periods(2025, 2030)
    salary         = depends(SalaryModel)   # bridge to Layer 1
    savings_rate   = glob(0.15)

    @row
    def savings(self, t):
        return self.salary.net(t) * self.savings_rate

    @row
    def spending(self, t):
        return self.salary.net(t) * (1 - self.savings_rate)

    @scalar
    def total_savings(self):
        return sum(self.savings(t) for t in self.time)
```

### 13.3 Running

```bash
expression run
```

Output:

```
✓ Discovered 2 models: SalaryModel -> BudgetModel
  ✓ Solved SalaryModel (2 rows, 12 cells)
  ✓ Solved BudgetModel (2 rows, 12 cells; 1 scalar)
✓ Wrote outputs/result.json
```

The discovery line shows the topological order — `SalaryModel` is solved first because `BudgetModel` depends on it.

### 13.4 Dependency ordering

`expression run` builds a directed graph from the `depends()` declarations between models in the file and topologically sorts it. You never specify an entry point — the solver figures out who needs whom. Models with no inter-dependencies between them are discovered in definition order.

If a cycle exists (Model A depends on Model B and Model B depends on Model A), `expression run` exits with a clear error:

```
✗ Circular dependency between models: SalaryModel -> BudgetModel -> SalaryModel
  Remove the cycle — models in a circular chain cannot be solved.
```

Cross-model cycles within `depends()` chains declared inside the same class are also caught at class-definition time (existing behavior, unchanged).

### 13.5 Inspecting cells

The `show` command searches all models by default:

```bash
expression show 'gross[2026]'             # searches all models
expression show 'SalaryModel.gross[2026]' # qualified: specific model
expression show 'BudgetModel.savings'     # whole row across all periods
```

### 13.6 Combined `result.json`

`outputs/result.json` always uses the multi-model shape:

```json
{
  "models": [
    {
      "model": { "name": "SalaryModel", ... },
      "inputs": { "base_salary": { "value": 55000, ... } },
      "tables": [ { "name": "gross", "results": { "2025": 55000, ... } } ],
      "scalars": []
    },
    {
      "model": { "name": "BudgetModel", ... },
      "inputs": { "savings_rate": { "value": 0.15, ... } },
      "tables": [ { "name": "savings", ... }, { "name": "spending", ... } ],
      "scalars": [ { "name": "total_savings", ... } ]
    }
  ]
}
```

`expression describe` also covers all models in the `models` list of `outputs/model.json`.

### 13.7 Overrides with multiple models

Without a scope qualifier, an override applies to every model that has a row or glob with that name:

```bash
expression overrides add raise_rate 0.05 --reason "optimistic scenario"
```

To restrict to one model:

```bash
expression overrides add raise_rate 0.05 --model-name SalaryModel --reason "optimistic scenario"
```

The `--model-name` flag writes a `model = "SalaryModel"` field to `overrides.toml` so the override is ignored when solving other models.

### 13.8 Snapshots and diff

When multiple models are solved, `expression snapshot accept` writes keys prefixed by model name:

```
SalaryModel.gross[2025]   = 55000
BudgetModel.savings[2025] = 5940.0
```

`expression diff` then shows drift per model, scoped correctly.

### 13.9 Multi-file mode

For shared upstream models, the multi-file pattern is unchanged:

```python
# pnl/expression.py
from expression import Model, depends, periods, row
from costs.expression import Costs  # explicit import

class PnL(Model):
    time  = periods(2024, 2026)
    costs = depends(Costs)

    @row
    def margin(self, t):
        return self.revenue(t) - self.costs.total_cost(t)
```

`expression run` in `pnl/` discovers only `PnL` (one model), solves it, and resolves `Costs` lazily via `depends()` exactly as before. The multi-file and same-file patterns compose naturally.

---

## 14. Excel import / export

### 13.1 Import

```bash
expression import quarterly.xlsx --out my_quarterly --classname Quarterly
```

The importer:
1. Reads the workbook with `openpyxl`.
2. Detects the time axis (header row of years/dates), globals (named cells), and row-shaped formula bands.
3. Emits a Layer-1 `expression.py` skeleton plus a `expression.md` with an **Issues found** section listing anything ambiguous.
4. Records auto-tests so the import only "succeeds" if every original cell value matches the generated solve.

This is non-interactive in Phase 2; Phase 3 wires it into the agent loop so questions can be asked. Either way, the contract is: **the imported model reads better than the original Excel** — the agent will restructure layout-driven logic into clean DAG form rather than transliterating it.

### 13.2 Export

```bash
expression export                        # → outputs/model.xlsx
expression export --out budget.xlsx
expression export --skip-verify
expression export --tol 1e-6             # verification tolerance
```

The exporter:
1. Solves the model.
2. Emits one row per `@row`, one column per period.
3. Writes a formula per cell mirroring the Python expression (e.g. `=B2*(1+$B$1)`).
4. Globals → named ranges. Datasets → hidden sheets. Scalars → a separate sheet. Overrides → hardcoded values with a comment cell.
5. **Verifies** by re-evaluating the produced workbook (via `formulas` if installed, else a built-in fallback) and diffing against the in-memory solve. Default tolerance `1e-9`. Failure prints the first ten mismatches and exits non-zero.

Round-trip fidelity is a values contract, not a formatting one.

---

## 15. Printing

`model print` is the cheapest way to eyeball results.

```bash
$ expression print
        2024    2025    2026    2027    2028
budget   100   105.0  110.25  115.76  121.55

irr = 0.2847
npv = 4312847.55
```

Use `-f csv` to pipe into anything else.

Inside Python: `model.format_table()` and `model.format_csv()` produce the same strings, after `solve()`.

---

## 16. The agent loop

`model agent` launches the interactive loop the framework was built around. It:

- Loads the bundled skills (`model/skills/*/SKILL.md`).
- Snapshots your workspace into a system prompt (file tree, `expression.md`, recent traces).
- Talks to a *harness* (Anthropic API by default; Claude Code or Codex via opt-in).
- Exposes three tools to the model: `read_file`, `write_file`, `run_model`.
- Confirms each *write* or *run_model* call before executing (skip with `--yes`).
- Streams every event to `.model/trace/<session>.jsonl` for replay.

### 15.1 Quickstart

```bash
export ANTHROPIC_API_KEY=sk-ant-…
model agent
» add a cogs row at 40% of budget and run

[tool] write_file({"path": "expression.py", …})
Proceed? [y/N] y
[tool] run_model({"subcommand": "run"})
Proceed? [y/N] y
…
```

### 15.2 Flags

| Flag | Meaning |
|---|---|
| `--workspace .` | Workspace root (default: cwd) |
| `--harness anthropic-api` | Harness backend (`anthropic-api` or `claude-code`) |
| `--yes`, `-y` | Auto-approve every tool call |
| `--message "…"`, `-m` | Send one opening message and exit after the reply (good for scripting) |

### 15.3 The agent's discipline

The default system prompt instructs the agent to:

- Make **one** small change at a time, then `expression run` and check the diff.
- Never bake hardcoded values into formulas — record them as overrides.
- After any code change, run `expression run` (and `expression test` if tests exist).
- Reference cells in backticks (so `expression doc sync` can pick them up).

Skills (§16) layer in stricter rules: bottom-up modeling, override discipline, parameter elicitation, etc. You can add or edit skills without touching code.

### 15.4 Plugins for Claude Code and Codex

The same skills ship as a self-contained plugin for **Claude Code** and
**Codex** — that is the supported way to drive `model` from an LLM.
Skills appear under `/expression:<skill-name>` and slash commands wrap the
common CLI verbs (`/expression:run`, `/expression:diff`, `/expression:show`,
`/expression:explain`, `/expression:export`). Each plugin bundles a
`expression-framework` skill (discipline + CLI reference) and the long-form
spec/tutorial under `reference/`, so the in-host agent has everything it
needs without a framework checkout.

See `docs/PLUGINS.md` for the install and dev loop.

---

## 17. Skills

A skill is an [Anthropic-format](https://github.com/anthropics/skills) directory with a `SKILL.md` file:

```
src/model/skills/<skill-name>/
└── SKILL.md
```

```markdown
---
name: bottom-up-modeling
description: Build models from the leaves upward. Don't start with the answer.
---
When the user describes a new model, do **not** start by writing the row that
answers their question. Start at the leaves:
1. List the inputs.
2. List the assumptions.
3. Sketch the dependency tree.
…
```

The agent concatenates every loaded skill's body into the system prompt.

### 16.1 Bundled skills

| Skill | What it enforces |
|---|---|
| `bottom-up-modeling` | Start at leaves; don't jump to the headline number. |
| `small-step-iteration` | One change → run → diff → commit. No multi-row rewrites. |
| `parameter-elicitation` | Ask which 2-5 globals the user will tweak; give them prominent placement. |
| `circularity-resolution` | Walk the user through breaking a cycle (lag / split / simplify). |
| `override-discipline` | Hardcoded value spotted? Convert to recorded override. |
| `excel-fidelity` | On export, diff in-memory solve against the produced `.xlsx`. |
| `import-excel` | Use `openpyxl`; ask about ambiguous formulas; flag TODOs in `expression.md`. |
| `harness-adapter` | Contract for plugging in a new LLM harness. |

### 16.2 Adding your own

Drop a folder under `src/model/skills/<your-skill>/` with a `SKILL.md`. It's picked up the next time `model agent` starts. Or pass `LoopConfig(skills_dir=Path(".my-skills"))` in code if you embed the loop.

Skills are static markdown — no Python required.

---

## 18. Harnesses — Claude Code, Codex, your own

A harness is what drives the conversation. Two ship today:

### 17.1 `anthropic-api` (default)

Talks directly to the Anthropic API via the `anthropic` SDK. Owns the tool-use round-trip; the loop sees and confirms every tool call.

Setup:

```bash
uv add 'expression[agent]'
export ANTHROPIC_API_KEY=sk-ant-…
model agent
```

Tunables:
- `MODEL_AGENT_MODEL` — model id (default `claude-sonnet-4-6`).
- The system prompt is sent with `cache_control: ephemeral` so re-runs within the 5-min TTL hit the prompt cache.

### 17.2 `claude-code`

Shells out to a local `claude` CLI (Claude Code). Use this when you'd rather have Claude Code manage its own tool loop, file edits, and model session.

```bash
# install Claude Code: https://docs.claude.com/en/docs/claude-code
claude /login
model agent --harness=claude-code
```

Because Claude Code owns its own tools, the harness returns `supports_tools()=False` and the loop treats responses as plain assistant prose. You drive edits the way you would in Claude Code; `model agent` becomes a thin wrapper that wires in the framework's system prompt + skills.

Override the binary path with `MODEL_AGENT_CLAUDE_CMD`.

### 17.3 Codex / OpenAI / your own

The harness contract is two methods (`harness-adapter` skill has the full template):

```python
from model.agent.harness import (
    Harness, HarnessResponse, Message, ToolCall, ToolSpec, register_harness,
)

class CodexHarness:
    name = "codex"

    def __init__(self):
        from openai import OpenAI            # lazy import
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY")
        self._client = OpenAI()

    def supports_tools(self) -> bool:
        return True   # if you wire up function-calling

    def chat(self, messages, system, tools) -> HarnessResponse:
        # translate to OpenAI schema, call, translate back
        ...

register_harness("codex", CodexHarness)
```

Import the module in `src/model/agent/__init__.py` (or your own bootstrap), and `model agent --harness=codex` works.

Guidelines (paraphrased from `harness-adapter` skill):
- Lazy-import provider SDKs.
- Validate config in `__init__` — fail fast.
- Cache the system prompt if your provider supports it.
- Keep harnesses pure; let the loop dispatch tools.

---

## 19. Traces and debugging the agent

Every agent session writes JSONL events to `.model/trace/<timestamp>.jsonl`:

```json
{"ts": …, "kind": "loop.start", "harness": "anthropic-api", "tools": ["read_file", "write_file", "run_model"]}
{"ts": …, "kind": "user.message", "text": "add a cogs row…"}
{"ts": …, "kind": "harness.response", "text": "…", "tool_calls": […], "stop_reason": "tool_use"}
{"ts": …, "kind": "tool.result", "name": "run_model", "result_preview": "✓ Solved…"}
{"ts": …, "kind": "loop.end", "turns": 4}
```

Useful with `jq`:

```bash
jq -c 'select(.kind=="harness.response") | {text, stop_reason}' .model/trace/*.jsonl
```

Programmatic access:

```python
from expression import Tracer
with Tracer(workspace) as tr:
    tr.event("custom", note="something happened")
```

Outside a `with` block, `Tracer.event()` still appends — useful in CLI commands.

---

## 20. Cheatsheet

### CLI surface

```
expression init <name>                Create a new model folder.
expression run [--mode=eager]         Discover all models, solve in DAG order, write outputs/result.json.
expression show <row>[<period>]       Print one cell or a row (searches all models).
expression show Model.row[period]     Qualified show: restrict to a specific model.
expression print [-f table|csv]       Render all models as tables (separator between each).
expression explain <row|scalar>       Show the desugared form + dependencies.
expression describe [--out f.json]    Export all model definitions (DAG, source, mermaid).
expression export [--out f.xlsx]      Render to .xlsx, verify values match.
expression import <f.xlsx>            Convert Excel → expression.py + expression.md.
expression diff                       Compare current solve to .model/snapshot.json.
expression snapshot accept            Pin the current solve as the new snapshot.
expression overrides add [--model-name X]   Manage overrides.toml (--model-name scopes to one model).
expression overrides list|rm|clear    Inspect / remove overrides.
expression doc sync                   Report drift between expression.py and expression.md.
expression agent [--harness=…] [-y]   Launch the interactive agent loop.
```

### DSL primitives

```python
from expression import (
    Model, row, scalar, glob, periods, dim, matrix, depends,
    dataset, xl, register,
)
```

| Primitive | Use |
|---|---|
| `Model` | Base class for your model. `class X(Model, sugar=False): …` opts out of Layer-2. |
| `periods(start, end)` | Inclusive integer-period axis. |
| `glob(default, doc=…)` | Named global. |
| `dim([…])` | Categorical axis. |
| `matrix(*axes, default=…)` | Indexed parameter table. |
| `@row` | Series row. `@row(over=[…])` for multi-dim. |
| `@scalar` | Aggregate row (one value). |
| `depends(OtherModel)` | Cross-model dependency; gives a *solved* upstream instance. |
| `dataset.csv(path, index=…)` | Class-level CSV input. |
| `dataset.from_row(model, row, columns=…)` | Build a `Dataset` from a solved row. |
| `xl.<fn>` | Excel-flavoured function library. |
| `xl.register` / `register` | Add a function to the `xl` namespace. |

Formula helpers should use the Python standard library unless the workspace
explicitly installs an optional package. The default framework environment
does not include heavy dependencies such as SciPy, so examples that need IRR
or root-finding should either use a small local helper or declare/install the
dependency first.

### Layer-2 sugar (inside `@row` / `@scalar` with no positional args)

```
budget[first] = …                # guard: t == time.first
budget[last]  = …                # guard: t == time.last
budget[2024]  = …                # guard: t == 2024
budget[n]     = …                # default
budget[n-1]                      # lag one period
budget[:]                        # full series
budget[2024:2027]                # inclusive window
growth_rate                      # bare global → self.growth_rate
```

### Iteration loop (the agent's contract)

```
edit  →  expression run  →  expression diff  →  expression test  →  commit
```

Don't skip steps. The diff is the safety net.

---

## What to read next

- `SPECIFICATION.md` (project root) — the full PRD with rationale.
- `src/model/skills/` — the skill bodies the agent loads.
- `src/model/xl.py` — the function library.
- `demo/carry/` — a worked growth-equity example.
