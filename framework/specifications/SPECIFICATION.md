# model — PRD

> A CLI for modeling Excel-like spreadsheets as Python DAGs, with an agentic loop on top so the user never opens Excel again.

---

## 1. Vision & non-goals

**Vision.** Excel models are equations. They have variables, periods, lookups, parameters, and (mostly) form a DAG. model represents that DAG in a tiny Python DSL, ships a CLI to import/edit/run/export it, and an agent (Claude Code, Codex, etc.) drives the iteration loop. The model is the source of truth; Excel becomes an export format.

**Non-goals (v1).**
- Not a full Excel runtime (no charts, no pivot tables, no VBA).
- Not a circular-solver. Models must be a DAG. Circular references are reported as errors with the cycle highlighted.
- Not a UI. CLI + files only. Agents are the "UI."
- Not a scientific computing tool. NumPy is an implementation detail, not exposed.

**Guiding principle.** *Extreme simplicity, with power earned through composition, not features.* Every feature added needs to justify its complexity against this principle. When in doubt, cut it.

---

## 2. Core concepts

| Concept | Excel analog | model representation |
|---|---|---|
| Cell | `B2` | A value at `(row, period)` or `(row, dim_a, dim_b)` |
| Row of formulas | row 2 dragged across | `@row` function |
| Named cell | named range | `glob(...)` |
| Lookup table | `VLOOKUP` against another sheet | `dataset(...)` or `matrix(...)` |
| Manual override | typing over a formula | `override("budget", 2023, 150)` — **recorded**, not edited in place |
| Model file | `.xlsx` | `model.py` + `model.md` |

**Key invariant:** the model is a DAG. `solve()` is a topological evaluation.

---

## 3. The DSL

### 3.1 Two layers, one language

- **Layer 1 — Pure Python (no magic).** Decorators only. Always works. Use this when debugging, generating, or when the AST rewrite would be confusing.
- **Layer 2 — AST sugar.** A small, well-scoped rewrite of `@row` function bodies that adds Excel-like notation (`budget[n-1]`, `budget[first]`, bare global names). Toggleable per-class via `class Foo(Model, sugar=False)`.

The agent should default to **Layer 2 for new code, Layer 1 when round-tripping unfamiliar Excel** (less surprise on import).

### 3.2 Layer 1 example (pure)

```python
from model import Model, row, glob, periods

class Budget(Model):
    time = periods(2020, 2024)
    growth_rate = glob(0.02)

    @row
    def budget(self, t):
        if t == self.time.first:
            return 100
        return self.budget(t - 1) * (1 + self.growth_rate)
```

### 3.3 Layer 2 example (sugar)

```python
class Budget(Model):
    time = periods(2020, 2024)
    growth_rate = glob(0.02)

    @row
    def budget():
        budget[first] = 100
        budget[n]     = budget[n-1] * (1 + growth_rate)
```

The AST rewrite is documented and inspectable: `model explain Budget.budget` prints the desugared Layer 1 form. **No hidden behavior.**

### 3.4 Multi-dimensional rows

```python
class Pricing(Model):
    products = dim(['A', 'B', 'C'])
    regions  = dim(['EU', 'US', 'APAC'])
    time     = periods(2024, 2026)

    base_price = matrix(products, regions, default=10.0)
    tax_rate   = matrix(regions, time, default=0.2)

    @row(over=[products, regions, time])
    def revenue(p, r, t):
        return base_price[p, r] * (1 + tax_rate[r, t]) * units_sold[p, r, t]
```

### 3.5 Scalar rows and the `xl.*` function library

Many Excel models need values that aggregate over a whole row: IRR, NPV, totals, ratios, max-drawdown. These are **scalar rows** — they produce one value, not a series.

```python
from model import Model, row, scalar, glob, periods, xl

class Investment(Model):
    time = periods(2024, 2030)
    discount_rate = glob(0.10)

    @row
    def cash_flow():
        cash_flow[first] = -1000
        cash_flow[n]     = 200 + cash_flow[n-1] * 0.05

    @row
    def cumulative():
        cumulative[first] = cash_flow[first]
        cumulative[n]     = cumulative[n-1] + cash_flow[n]

    @scalar
    def npv():
        return xl.npv(discount_rate, cash_flow[:])

    @scalar
    def irr():
        return xl.irr(cash_flow[:])

    @scalar
    def payback_year():
        return xl.first_where(cumulative[:], lambda x: x >= 0)
```

**Slicing notation (also part of the sugar):**

| Syntax | Meaning |
|---|---|
| `row[n]` | Value at the current period (only valid inside `@row`) |
| `row[n-k]` | Value k periods ago |
| `row[first]` / `row[last]` | First / last period value |
| `row[:]` | Full series as an array (any context) |
| `row[2024:2027]` | Inclusive window by period label |
| `row[:n]` | Series from start up to and including current period (running calcs) |

**The `xl` namespace.** A plain Python module of functions that take arrays/scalars and return arrays/scalars. The DSL doesn't know about them — they're just functions. Initial set covers the common Excel financial/statistical functions:

| Category | Functions |
|---|---|
| Financial | `npv`, `xnpv`, `irr`, `xirr`, `mirr`, `pmt`, `pv`, `fv`, `rate`, `nper` |
| Statistical | `sum`, `avg`, `min`, `max`, `stdev`, `var`, `percentile`, `median` |
| Logical | `if_`, `and_`, `or_`, `not_`, `iferror` |
| Lookup | `vlookup`, `index_match`, `xlookup` (operate on datasets/matrices) |
| Date | `eomonth`, `edate`, `yearfrac`, `workday` |
| Series | `cumsum`, `running_max`, `drawdown`, `first_where`, `last_where` |

**Extension is just Python.** Register a custom function and it joins the namespace:

```python
from model import register

@register
def sharpe(returns, risk_free=0.02):
    excess = [r - risk_free for r in returns]
    return xl.avg(excess) / xl.stdev(excess)

# usable anywhere as xl.sharpe(returns[:])
```

**Why scalar rows are first-class (not just `@row` returning a number):** they participate in the DAG with the same dependency tracking, get the same caching, show up in `model show` and `model diff`, and round-trip to Excel as a single named cell. Treating them differently lets the engine optimize and the agent reason about them clearly.

### 3.6 Datasets (input + output)

```python
class Forecast(Model):
    historical = dataset.csv("inputs/historical.csv", index="date")

    @row
    def forecast():
        forecast[first] = historical.last("revenue")
        forecast[n]     = forecast[n-1] * 1.05

    @output
    def projections():
        return dataset.from_row(forecast, columns=["year", "revenue"])
```

### 3.7 Overrides — first-class

Manual hardcoded overrides happen. They get **recorded** as data, not edited into formulas:

```python
# overrides.toml — sits next to model.py
[[override]]
row = "budget"
period = 2023
value = 150
reason = "Board adjustment Q4 2022"
author = "pietro"
```

`model run` applies these on top of the computed DAG. `model overrides list/add/remove/clear` manage them. **Never** edit formulas to bake in a one-time override — the agent enforces this.

### 3.8 Model-to-model dependencies

```python
# revenue.py
class Revenue(Model): ...

# pnl.py
from .revenue import Revenue

class PnL(Model):
    rev = depends(Revenue)

    @row
    def gross_profit():
        gross_profit[n] = rev.total[n] - cogs[n]
```

`depends()` adds the upstream model to the DAG. Circularity across `depends()` chains is detected at class-definition time.

### 3.9 Multiple models in one file

A single `sweet.py` may contain **any number of `Model` subclasses**. `sweet run` discovers all of them, builds a cross-model dependency graph from `depends()` declarations, topologically sorts the graph, and solves every model in dependency order. No "entry point" is needed.

```python
# sweet.py — two models in one file
class Salary(Model):
    time        = periods(2025, 2030)
    base_salary = glob(55_000.0)

    @row
    def gross(self, t): ...

class Budget(Model):
    time   = periods(2025, 2030)
    salary = depends(Salary)   # Salary solved first automatically

    @row
    def savings(self, t):
        return self.salary.gross(t) * 0.15
```

**Discovery rules:**

- All `Model` subclasses in the file are collected.
- A directed graph is built: for each `depends(Upstream)` where `Upstream` is also in the file, an edge `Upstream → Dependent` is added.
- The graph is topologically sorted. If a cycle exists, `sweet run` exits with a descriptive error naming the cycle.
- Models with no inter-dependencies are processed in definition order.

**Output shape:** `outputs/result.json` always uses `{"models": [...]}` with one entry per model. `outputs/model.json` similarly lists all models.

**Overrides scoping:** `overrides.toml` entries may carry an optional `model` field to restrict application to a named `Model` class. Without it, the override applies to every model that has a matching row or glob.

**Multi-file:** Unchanged. `import` the upstream file and declare `depends()` — `sweet run` in the downstream workspace discovers and solves the one `Model` in that file, resolving the upstream lazily as before.

---

## 4. Execution models

The PRD documents all three. **v1 ships #2 (eager).** #3 is a v2 add.

### 4.1 Lazy DAG resolution
Compute only what's asked. `model.budget[2023]` triggers exactly the chain needed. Best for huge models. Adds caching complexity; deferred.

### 4.2 Eager full computation (v1)
`model.solve()` topologically sorts the DAG and computes every cell. Simple, predictable, debuggable. Good enough for models up to ~1M cells, which covers >95% of Excel use.

### 4.3 Reactive / incremental (v2)
On change, recompute only downstream cells. Requires a dependency tracker per cell and dirty-bit propagation. Powerful for the "tweak a parameter" loop, but adds real complexity. Layer it on once #2 is stable.

The execution mode is a CLI flag: `model run --mode=eager|lazy|reactive`. The default is `eager`.

---

## 5. Files & layout

A model lives in a folder:

```
my_model/
├── model.md              # human-readable spec, kept in sync with code
├── model.py              # the Model class (or multiple classes)
├── overrides.toml        # recorded manual overrides
├── inputs/               # CSV/Parquet/JSON datasets the model reads
│   └── historical.csv
├── outputs/              # produced datasets and result snapshots
│   ├── result.json       # last solve, all cells
│   └── result.xlsx       # exported Excel (on demand)
├── tests/                # pytest cases
│   └── test_budget.py
└── .model/
    ├── lockfile.json     # hash of model.py + inputs at last solve
    └── trace/            # per-run computation traces (for the agent)
```

For multi-file models, `model.py` can `from .submodule import X`. The CLI auto-discovers all `Model` subclasses.

---

## 6. The `model.md` contract

`model.md` is **not** auto-generated from code comments. It's a human-readable specification that the agent **reconciles** with the code on every change. Structure:

```markdown
# Budget model

## Purpose
One paragraph: what business question does this answer?

## Inputs
- `growth_rate` (global, default 2%) — annual revenue growth
- `historical.csv` — last 3 years of actuals

## Outputs
- `budget[year]` — projected annual budget 2024–2028
- `cumulative[year]` — running total

## Logic
Plain prose explanation of how rows compute, what the assumptions are.

## Known issues / open questions
- [ ] Growth rate flat — should it vary by year?
- [x] Resolved 2026-05-01: confirmed seed value is 100, not 95

## Overrides
Listed automatically from overrides.toml with reasons.

## Changelog
Append-only list of material changes.
```

**Reconciliation step.** On every `model run`, the CLI checks: do all rows in `model.py` appear in `model.md`? Are there mentions in `model.md` of rows that don't exist? If drift is detected, the run **succeeds but warns**, and the agent is prompted to reconcile. `model doc sync` does this interactively.

---

## 7. CLI surface

Keep it small. Every command must earn its place.

```
model init <name>                Create a new model folder
model import <file.xlsx>         Convert Excel → model.py + model.md (interactive)
model export [--out file.xlsx]   Render model → Excel, verify values match
model run [--mode=eager]         Solve the model, write outputs/result.json
model show <row>[<period>]       Print one cell or row (e.g., `model show budget[2024]`)
model explain <row>              Show desugared code + dependency chain
model diff                       Compare current solve vs last snapshot
model test                       Run the test battery (pytest under the hood)
model doc sync                   Reconcile model.md with model.py
model overrides {add|list|rm}    Manage overrides.toml
model agent                      Launch interactive agent mode (drives Claude Code/Codex)
```

That's it. No subcommand sprawl.

---

## 8. The agent loop

The CLI is the substrate; agents are the interface for non-trivial work.

### 8.1 Skills the agent ships with

Stored in `model/skills/` (following Anthropic's skill format). Initial set:

| Skill | When triggered | What it enforces |
|---|---|---|
| `import-excel` | `model import` | Use `openpyxl` for read; ask user about ambiguous formulas; split unclear rows into "TODO" sections in model.md |
| `bottom-up-modeling` | New model creation | Ask: what are the leaf inputs? Build up from there. Don't start with the answer. |
| `small-step-iteration` | Always, during edits | Make one change, run, verify, commit. No multi-row rewrites without solve-between-steps. |
| `parameter-elicitation` | Interactive mode | Ask the user which 2-5 globals they'll most likely tweak. These get prominent placement and dedicated tests. |
| `circularity-resolution` | Cycle detected | Walk the user through breaking the cycle (lag, simplification, or split). |
| `override-discipline` | Hardcoded value spotted in formula | Suggest converting to recorded override. |
| `excel-fidelity` | `model export` | Compute values in Python, compute again from the produced .xlsx via openpyxl's formula evaluation, diff. |

### 8.2 Interactive mode flow

```
$ model agent
> What are we modeling? (free text)
> What's the time horizon, if any?
> What are the 1-3 numbers you'll most want to tweak?
> Bottom-up or top-down? (default: bottom-up)
> [agent proposes file structure, shows it, asks for confirmation]
> [agent generates model.py + model.md skeleton]
> [enters edit loop: agent suggests next row, user confirms or redirects]
```

Critical: **the agent restructures aggressively when importing from Excel.** Excel models often have layout-driven logic that's wrong from a modeling standpoint. The agent flags these and proposes the *right* structure, not a transliteration.

### 8.3 The iteration loop

```
edit → model run → model diff → model test → commit
```

Agents are instructed (via skills) to never skip steps. `model diff` is the safety net — it prints the cells that changed since the last snapshot and forces a "yes this is intended" check.

---

## 9. Excel import / export

### 9.1 Import (Excel → model)

Pipeline:
1. `openpyxl` reads cells, formulas, named ranges, sheet structure.
2. Heuristic pass: detect the time-axis (usually a header row of years/dates), detect dimension-axes, detect global named cells.
3. Each formula row is parsed (use `formulas` library — `pip install formulas` — or `xlcalculator`) into an AST.
4. The agent presents its interpretation row-by-row and asks for confirmation on ambiguous cases.
5. `model.md` is generated with a "Issues found" section listing things the agent couldn't infer.
6. A `tests/test_import.py` is auto-created comparing every cell of the original `.xlsx` to the generated model's `solve()`. **Import succeeds only if this test passes.**

Leverage existing skills: the [Anthropic xlsx skill](https://github.com/anthropics/skills/tree/main/skills/xlsx) and [financial-services skills](https://github.com/anthropics/financial-services). The agent reads these as part of the import skill bundle.

### 9.2 Export (model → Excel)

Pipeline:
1. Solve the model.
2. For each row, emit a header (period or dimension labels) and a formula per cell that mirrors the Python expression. (e.g., `budget[n] = budget[n-1] * (1+growth_rate)` becomes `=B2*(1+$B$1)` in the appropriate cell.)
3. Globals become named ranges.
4. Datasets become hidden sheets.
5. Overrides become hardcoded values with a comment cell explaining the override reason.
6. **Verification step:** open the produced `.xlsx` with `openpyxl --data_only=False`, evaluate the formulas using `formulas` library, diff against the in-memory solve. Tolerance: configurable, default `1e-9` relative.
7. If verification fails, the export errors with the first 10 mismatched cells.

**Round-trip fidelity contract:** values must match within tolerance. Formatting (colors, fonts, column widths) is best-effort; layout is functional but not pixel-identical.

---

## 10. Test batteries

Tests are not optional — they are how the agent knows it didn't break anything. Every model gets:

### 10.1 Auto-generated tests (on `model init` / `import`)
- `test_solve.py` — model solves without error, all cells produce numeric (or expected type) results
- `test_dag.py` — no circular dependencies, no orphan rows
- `test_excel_roundtrip.py` — for imported models, every original cell value matches solved value
- `test_overrides.py` — overrides apply correctly and don't break downstream

### 10.2 Snapshot tests
`model run` always writes `outputs/result.json`. A `test_snapshot.py` compares current solve to the committed snapshot. Diffs are flagged. To accept: `model snapshot accept`.

### 10.3 Property-based tests (encouraged, not required)
Using `hypothesis`, the agent can suggest invariants:
- Monotonic rows: `budget` is non-decreasing
- Conservation: `total[n] == sum(parts[n])`
- Bounded: `tax_rate` always in `[0, 1]`

### 10.4 Parameter-sweep tests
For each global the user marked as "key parameter," generate a sweep test: solve at 0.5×, 1×, 2× the default and assert no errors + sensible directionality.

### 10.5 The "agent verification" test
A meta-test the agent must pass before proposing a change: run `model test` before AND after, both must be green. Enforced via skill, not code.

---

## 11. Tooling choices (for the agent building this)

| Concern | Pick | Why |
|---|---|---|
| Language | Python 3.11+ | Match-case, better error locations, fast enough |
| CLI framework | **Typer** | Type-hinted, generates `--help` cleanly, smaller than Click |
| Excel read/write | **openpyxl** | Mature, formula-aware. NOT pandas (loses formulas). |
| Excel formula evaluation | **formulas** (`pip install formulas`) | For round-trip verification. Fall back to `xlcalculator` if needed. |
| AST manipulation | stdlib `ast` + `astor` | Keep the sugar layer transparent and inspectable |
| DAG | **networkx** | Topological sort, cycle detection out of the box |
| Data | **polars** for datasets | Fast, no pandas baggage, lazy eval fits the model |
| Numerics | stdlib `decimal` for currency, `float` otherwise | Configurable per-row via `@row(precision='decimal')` |
| Testing | **pytest** + **hypothesis** | Standard |
| Snapshot diffing | **deepdiff** | Pretty cell-level diffs |
| Packaging | **uv** + `pyproject.toml` | Fast, modern, no setup.py |
| Type checking | **pyright** strict | Catch DSL misuse early |
| Lint/format | **ruff** | One tool, fast |
| Agent skills format | Anthropic skills convention | `SKILL.md` + supporting files per skill |
| Logging | **structlog** | JSON logs the agent can parse from `.model/trace/` |

**Hard "don't use" list:** pandas (formula loss), xlsxwriter (write-only, breaks round-trip), sympy (overkill, slow).

---

## 12. Worked examples

### 12.1 Example 1 — Simple budget (the "hello world")

```python
# my_budget/model.py
from model import Model, row, glob, periods

class Budget(Model):
    time = periods(2024, 2028)
    seed = glob(100, doc="Starting budget in $K")
    growth_rate = glob(0.05, doc="Annual growth rate")

    @row
    def budget():
        budget[first] = seed
        budget[n]     = budget[n-1] * (1 + growth_rate)
```

```bash
$ model run
✓ DAG validated (1 row, 5 cells)
✓ Solved in 0.4ms
budget: [100.0, 105.0, 110.25, 115.76, 121.55]

$ model show budget[2026]
budget[2026] = 110.25
  = budget[2025] * (1 + growth_rate)
  = 105.0 * (1 + 0.05)

$ model export --out budget.xlsx
✓ Exported to budget.xlsx
✓ Verified: all 5 cells match within tolerance
```

### 12.2 Example 2 — Multi-row dependency

```python
class PnL(Model):
    time = periods(2024, 2026)
    revenue_growth = glob(0.10)
    cogs_pct = glob(0.40)

    @row
    def revenue():
        revenue[first] = 1000
        revenue[n]     = revenue[n-1] * (1 + revenue_growth)

    @row
    def cogs():
        cogs[t] = revenue[t] * cogs_pct

    @row
    def gross_profit():
        gross_profit[t] = revenue[t] - cogs[t]
```

`model explain gross_profit` shows:

```
gross_profit depends on: revenue, cogs
cogs depends on: revenue, cogs_pct (global)
revenue depends on: revenue_growth (global), self (lag)
```

### 12.3 Example 3 — Override

```bash
$ model overrides add revenue 2025 1500 --reason "New customer signed Q1 2025"
✓ Override recorded
$ model run
✓ Solved with 1 override
revenue: [1000, 1500, 1650]    # 2026 = 1500 * 1.10, not 1100*1.10
```

The formula stays clean. The override is data, versioned, explainable.

### 12.4 Example 4 — Lookup against a dataset

```python
class Pricing(Model):
    fx = dataset.csv("inputs/fx_rates.csv", index="currency")
    products = dim(['A', 'B'])
    time = periods(2024, 2026)

    base_price_eur = matrix(products, default={'A': 10, 'B': 25})

    @row(over=[products, time])
    def price_usd(p, t):
        return base_price_eur[p] * fx.lookup("EUR", "USD", at=t)
```

Any row with extra axis arguments must declare those axes in `@row(over=[...])`
in the same order as the function parameters. Bare `@row` is only for rows
over the model's `time` axis; `def drawdown(self, t, company)` with bare
`@row` will fail because the solver passes only `t`.

Examples should avoid optional heavy runtime dependencies unless they are
declared and installed by the workspace. Prefer stdlib helpers for small
financial math routines such as IRR/root finding, or explicitly add the
dependency before importing packages such as SciPy.

### 12.5 Example 5 — Investment with IRR / NPV / payback

```python
from model import Model, row, scalar, glob, periods, xl

class DealReturns(Model):
    time = periods(2024, 2031)
    initial_investment = glob(5_000_000)
    discount_rate = glob(0.12)
    exit_multiple = glob(2.5)

    @row
    def cash_flow():
        cash_flow[first] = -initial_investment
        cash_flow[2025]  = 200_000
        cash_flow[2026]  = 500_000
        cash_flow[2027]  = 800_000
        cash_flow[2028]  = 1_200_000
        cash_flow[2029]  = 1_500_000
        cash_flow[2030]  = 1_800_000
        cash_flow[last]  = 2_000_000 + initial_investment * exit_multiple

    @row
    def cumulative():
        cumulative[first] = cash_flow[first]
        cumulative[n]     = cumulative[n-1] + cash_flow[n]

    @scalar
    def npv():
        return xl.npv(discount_rate, cash_flow[:])

    @scalar
    def irr():
        return xl.irr(cash_flow[:])

    @scalar
    def moic():
        return xl.sum(cash_flow[1:]) / -cash_flow[first]

    @scalar
    def payback_year():
        return xl.first_where(cumulative[:], lambda x: x >= 0)
```

```bash
$ model run
✓ DAG validated (2 row × 8 periods + 4 scalars)
✓ Solved in 1.2ms
cash_flow:    [-5000000, 200000, 500000, 800000, 1200000, 1500000, 1800000, 14500000]
cumulative:   [-5000000, -4800000, -4300000, -3500000, -2300000, -800000, 1000000, 15500000]
npv:          4_312_847.55
irr:          0.2847   (28.47%)
moic:         4.10
payback_year: 2030

$ model show irr
irr = 0.2847
  = xl.irr(cash_flow[:])
  depends on: cash_flow (8 cells)
```

### 12.6 Example 6 — Cross-model composition

```python
# costs/model.py
class Costs(Model):
    time = periods(2024, 2026)
    @row
    def total_cost(): ...

# pnl/model.py
from costs.model import Costs

class PnL(Model):
    costs = depends(Costs)
    @row
    def margin():
        margin[t] = revenue[t] - costs.total_cost[t]
```

---

## 13. Build phases

### Phase 0 — Foundations (week 1-2)
- Repo scaffold, `uv` setup, pyproject, ruff/pyright config
- `Model` base class, `@row` decorator (Layer 1 only — no AST sugar yet)
- `glob()`, `periods()`, eager solver via `networkx`
- `model init`, `model run`, `model show`
- Test: example 12.1 works end to end

### Phase 1 — DSL completeness (week 3-4)
- AST sugar layer (Layer 2)
- `dim()`, `matrix()`, multi-dim `@row(over=...)`
- `dataset.csv()`, `dataset.from_row()`
- `depends()` for cross-model
- `overrides.toml` + `model overrides` CLI
- Tests for examples 12.2–12.5

### Phase 2 — Excel I/O (week 5-6)
- `model import` — formula parsing, dimension detection, agent prompts
- `model export` — formula generation, named ranges, verification
- Round-trip fidelity tests across a corpus of sample `.xlsx` files
- Integration with Anthropic xlsx skill

### Phase 3 — Agent loop (week 7-8)
- Skills directory + skill loader
- `model agent` interactive mode
- `model doc sync` for model.md reconciliation
- `model diff` and snapshot management
- Trace logging to `.model/trace/`

### Phase 4 — v2 candidates
- Reactive execution mode
- Web viewer for model.md + result preview (read-only)
- Sensitivity analysis: `model sweep growth_rate=0.01..0.10:0.01`
- Monte Carlo: `model mc revenue_growth=normal(0.05, 0.02) --n=10000`

---

## 14. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| AST sugar surprises users | High | Always-available `--explain` desugaring; sugar is opt-out per class |
| Excel import produces garbage on complex models | High | Agent asks lots of questions; failed-import is a feature, not a bug; "Issues found" section in model.md |
| Round-trip drift | Medium | Verification step on export is mandatory, not optional |
| Performance on large models (>100k cells) | Medium | Eager mode benchmarked at Phase 0; lazy mode is the escape hatch |
| Skill drift between Claude Code / Codex / others | Medium | Skills follow Anthropic's `SKILL.md` convention; portable |
| Scope creep into "Excel replacement" | High | This PRD is the contract. Re-read section 1 before adding features. |

---

## 15. Open questions for Pietro

1. **Currency / units.** Should the DSL have first-class units (`100 USD`, `5%`) or keep it numeric and let the user document? Lean: keep numeric for v1, add `units` library integration in v2.
2. **Model signing / audit.** For investment use, do we need cryptographic signing of the result.json + model.py hash? Could be a 1-day add.
3. **Multi-scenario.** `model run --scenario=base|upside|downside` with scenario-specific overrides. Worth v1 or defer?
4. **Excel formula coverage on import.** The `xl.*` namespace covers the common cases (financial: NPV/IRR/XIRR/MIRR/PMT, statistical, lookup, date, series). Suggested rule: if Excel uses a function in `xl.*`, map directly. If it uses something exotic (e.g., `SUMPRODUCT` with array tricks), the agent flags it, asks the user what the formula is *trying* to do, and writes a clean Python equivalent — often simpler. Goal: the imported model reads better than the original Excel.
5. **Notebook integration.** Jupyter cells that import a model and plot? Nice-to-have, but it's a slippery slope toward "Excel replacement." Lean: defer, document the pattern only.

---

## 16. Success criteria for v1

- [ ] A user can `model import` a 50-row Excel model and get a working `model.py` + `model.md` in under 10 minutes of agent dialogue.
- [ ] `model export` round-trips that model with all values matching to 1e-9.
- [ ] An agent (Claude Code) can take "increase the growth rate by 1% and add a new cost row" and complete it via the CLI, with tests passing, in under 5 minutes.
- [ ] `model.md` for that model is human-readable and accurate.
- [ ] Total LOC of model itself: < 5000 lines. (Simplicity check.)
