# Phase 1 — Proposed changes / clarifications to SPECIFICATION.md

Same purpose as `PHASE0_PROPOSED_CHANGES.md`: surface the design calls Phase 1
implementation made where the PRD didn't pin them down, plus deviations the
spec should ratify or push back on.

> Status legend: **[decision]** = chose one path; **[deviation]** = differs
> from PRD as written; **[question]** = needs your call.

Reads on top of Phase 0 doc — points 1-11 there still hold.

---

## 12. Layer-2 sugar: detection rule + scope walker [decision]

PRD §3.1 says sugar is opt-out per class via `class Foo(Model, sugar=False)`.
Phase 1 implements:

- **Per-class opt-out**: `class Foo(Model, sugar=False):` — passes the keyword
  through `__init_subclass__`, sugar transformation is skipped for that class.
- **Per-method detection**: a function written `def foo():` (no positional
  args) is treated as Layer-2 and rewritten. A function written
  `def foo(self, t):` is left alone. So Layer 1 and Layer 2 *coexist inside the
  same class* — a Phase-0 decision-#1 promise carried forward.

This deviates slightly from how the PRD reads (sugar = "all or nothing per
class"), but it's strictly more powerful and matches the spirit of "the agent
defaults to Layer 2 for new code, Layer 1 when round-tripping unfamiliar
Excel" (§3.1) — those two forms can now sit side-by-side.

**Proposal:** add a sentence to §3.1 making this explicit.

## 13. Layer-2 supported transformations [decision]

What's actually wired up in `src/model/sugar.py`:

| Layer 2 | Layer 1 |
|---|---|
| `def name():` | `def name(self, t):` (row) / `def name(self):` (scalar) |
| `name[first] = expr` | `if t == self.time.first: return expr` |
| `name[last] = expr` | `if t == self.time.last: return expr` |
| `name[2024] = expr` | `if t == 2024: return expr` |
| `name[n] = expr` / `name[t] = expr` | (default rule) `return expr` |
| `name[first]` (read) | `self.name(self.time.first)` |
| `name[n - k]` (read) | `self.name(t - k)` |
| `name[2024]` (read) | `self.name(2024)` |
| `name[:]` (read) | `self.series("name")` |
| `name[a:b]` (read) | `[self.name(p) for p in range(a, b+1)]` (inclusive) |
| Bare `growth_rate` | `self.growth_rate` (any model attribute name) |

**Out of scope for Phase 1:**
- `name[:n]` / `name[n:]` — running-window slices (PRD §3.5 table). Document as
  Phase 2 to keep the rewriter constrained.
- `xl.*` registration is import-time, not transformed by sugar.

The rewriter records a `Row.explicit_deps` set computed from the *Layer-2 AST*
(before rewriting) — subscripts and bare names that resolve to other rows
become DAG edges. The solver consults `explicit_deps` first, falling back to
the Phase-0 `self.<other_row>(...)` AST scan for Layer-1 functions. This is
needed because `cash_flow[:]` desugars to `self.series("cash_flow")` whose
string argument is invisible to the Phase-0 dep extractor.

**Proposal:** call out in §3.3 that "the AST rewrite is documented and
inspectable" implies the desugarer also pre-computes deps; otherwise Layer-2
slice forms are silently mis-ordered.

## 14. `model explain` command [decision]

PRD §7 lists `model explain <row>`. Phase 1 ships a working version backed by
`sugar.desugar_to_source()` which reproduces the Layer-1 form via
`ast.unparse`. Output:

```
$ model explain budget
# budget (row)
# depends on: growth_rate, seed

@row
def budget(self, t):
    if t == self.time.first:
        return self.seed
    return self.budget(t - 1) * (1 + self.growth_rate)
```

For Layer-1 functions (no rewrite happened), it falls back to
`inspect.getsource()`. Dependency chain printing (PRD §3.3, §12.5) is shallow:
direct deps only. Recursive / transitive printing is a Phase 3 nicety.

## 15. `@scalar` cell key uses `(name, None)` [decision]

PRD §3.5 says scalars "participate in the DAG with the same dependency
tracking, get the same caching, show up in `model show` and `model diff`".
Phase 1 stores them in the same `_cells` dict as rows, keyed `(name, None)`,
so existing inspection helpers (`m.cell("npv", None)`, `m.has_cell("npv",
None)`) work uniformly.

Side effect: `model.series(scalar_name)` raises `ModelError` because scalars
aren't in `_rows`. That feels right — scalars don't *have* a series.

## 16. `xl.*` namespace coverage and conventions [decision]

`src/model/xl.py` ships the PRD §3.5 table. Notable choices:

- `xl.npv(rate, cash_flows)` follows Excel: cash flow at index 0 is discounted
  by *one* period. The "investment-at-t0" pattern needs
  `cf[0] + xl.npv(rate, cf[1:])` — this is what PRD example 12.5 implicitly
  needs and what the Phase-1 tests exercise.
- `xl.first_where` returns an integer *index*, not a period label. Mapping
  index → period requires the model's `time` axis. Keeping it index-based
  matches `xl.cumsum`/`xl.running_max`/`xl.drawdown` (also index-aligned) and
  composes with `model.series("...")`.
- `xl.register(fn)` injects into the `xl` namespace by mutating `globals()`.
  Simple and matches PRD's "register a custom function and it joins the
  namespace" wording. Tradeoff: `xl.foo` shows up only after import-order
  registration; that's fine for our use.
- `xl.iferror(thunk, fallback)` takes a *callable*, not an expression. Excel's
  IFERROR is a special form; the Python rendering needs a thunk because the
  language has no lazy-by-default eval.

**Proposal:** note in §3.5 that `iferror` takes a thunk.

## 17. Overrides applied pre-solve via cell pre-population [decision]

PRD §3.7 says overrides "apply on top of the computed DAG". Phase 1 implements
this by writing override values into `model._cells` *before* the topological
evaluation. Because `BoundRow.__call__` checks the cache first, downstream
rows naturally read the overridden value. Glob overrides go through the
existing Phase-0 `Glob.__set__` path (instance-level override).

This means an override doesn't *replace* a formula — the formula simply
isn't called for that cell. Matches the PRD's "the formula stays clean. The
override is data, versioned, explainable" intent.

`overrides.toml` format:

```toml
[[override]]
row = "revenue"
period = 2025
value = 1500
reason = "New customer signed Q1 2025"
author = "pietro"

[[override]]
glob = "growth_rate"
value = 0.07
```

**Proposal:** standardize this in the PRD §3.7 example (currently shows only
the row form).

## 18. `dataset.csv()` is stdlib-backed in Phase 1 [deviation]

PRD §11 specifies `polars` for datasets. Phase 1 uses stdlib `csv` instead —
zero deps, the API surface (`dataset.csv(path, index=)`, `.lookup`, `.last`,
`.first`, `.column`, `.rows`) is unchanged, so swapping to polars is a
drop-in upgrade. Reasons: (a) keeps install footprint tiny for Phase 1
adopters; (b) polars buys nothing yet — we're not doing dataframe
operations, just keyed-row lookup and last/first scans.

When does it matter? Once Phase 2 import/export starts loading 100k+ row
historical CSVs, polars columnar ops will be measurably faster. The swap is
a one-file change.

**Proposal:** treat the dependency choice in §11 as advisory until size
demands it.

## 19. Multi-dim cell keys are flat tuples [decision]

A 1-D row caches at `(row_name, t)`. A multi-dim row from `@row(over=[p, r,
t])` caches at `(row_name, p, r, t)` (flat, not nested). `model.cell("rev",
(p, r, t))` accepts a tuple and unpacks. Rationale: lookups remain
constant-time, JSON-serializable (flat-string-key form `"rev[p, r, t]"`), and
deepdiff-friendly when snapshot tests land in Phase 2.

**Caveat:** mixing 1-D and multi-dim rows in the same model works; series
lookup `model.series("rev")` is single-axis only. Multi-dim "give me all the
cells" is just `m.cells()` filtered.

## 20. `Matrix` is read-write per instance [decision]

`matrix(products, regions, default=10.0)` is a class-level *spec*; on
instance access `self.base_price` returns a `_MatrixView` that reads from a
per-instance overrides dict and falls back to the spec's default. So
`m.base_price["A", "EU"] = 25.0` cleanly customizes one cell without
mutating the class. Same pattern as Glob's instance-level override (Phase 0
decision #3).

The PRD §3.4 example writes `base_price = matrix(products, regions,
default=10.0)` — implying read-only. Our read-write semantics is strictly
more powerful and needed for parameter sweeps and import workflows.

**Proposal:** add to §3.4 that matrices support per-instance assignment for
sensitivity / import.

## 21. `depends()` solves upstream eagerly + caches [decision]

`self.costs` triggers an upstream `Costs().solve()` once and caches the
solved instance on the dependent model. This:

- Keeps the contract simple: by the time any `self.costs.total_cost(t)` runs,
  upstream is fully solved.
- Avoids weaving upstream rows into the dependent's DAG (which would conflate
  identity / cell-key namespaces).
- Pays a small cost on first access — fine for Phase 1.

Cycles across model classes are detected at *class definition time* (in
`__init_subclass__` via `_check_cross_model_cycle`), so circular `depends()`
graphs can't even be imported. Matches PRD §3.8 wording.

A consequence: changes to upstream globals after the dependent has touched
`self.costs` won't propagate (the cached instance was solved with old
values). A "rebuild" hook is Phase-3 territory; document the gotcha.

**Proposal:** call out the once-and-cache semantics in §3.8.

## 22. Pyright relaxations for the DSL pattern [deviation]

Phase 0's pyright relaxations (§11 networkx generics) are extended in Phase
1 to *warning* (not silent) for these strict-mode rules:

- `reportUndefinedVariable` — Layer-2 row bodies use `first`, `n`, `t`, and
  bare row names that don't resolve at type-check time but are rewritten by
  the AST sugar.
- `reportIncompatibleMethodOverride` / `reportAssignmentType` —
  `time = periods(...)` shadows `Model.time` (declared as `@property`).
  This pattern is *idiomatic* per PRD §3.2.
- `reportArgumentType` — same shadow leaks into `over=[products, time]`
  call sites.
- `reportPrivateUsage` — `solver.py`, `sugar.py`, `overrides.py`, and tests
  intentionally read state populated by `Model.__init_subclass__`.
- `reportUnnecessaryIsInstance`, `reportUnnecessaryComparison`,
  `reportAttributeAccessIssue`, `reportUnusedClass` — defensive checks +
  test-time class scaffolding.

Net result: 0 type *errors* on `uv run pyright`; warnings tolerated. Strict
mode for the rest of the codebase still applies.

**Proposal:** §11 footnote that the DSL pattern requires these relaxations.
The alternative is custom stub files for `model.core` and a property-free
`time` API, both of which add complexity.

## 23. `model init` template stays Layer-1 [decision, carried forward]

Phase 0 decision #9: the `model init` template uses Layer 1. With Layer 2
implemented in Phase 1, we *could* switch the template. We don't, because:

- Layer 1 reads more like ordinary Python and is friendlier for first-time
  users.
- The agent (per PRD §3.1) "defaults to Layer 2 for new code" — but the
  template is a *user-facing* artifact, so it should bias toward "obvious"
  over "concise."

Trivial to flip later via one constant in `cli.py`.

**Proposal:** PRD §7 currently says "Create a new model folder" — add a
sentence stating the template is Layer 1 by default.

## 24. CLI: `model explain` and `model overrides` [decision]

Phase 1 ships:

- `model explain <row|scalar>` — desugared form + direct deps (§7).
- `model overrides {add|list|rm|clear}` — TOML-backed (§7).

Argument parsing for `overrides add`: `target`, `period`, `value` (positional
in that order), `--glob` flag, `--reason`, `--author`. Periods omitted via
empty-string positional. Adding a `model overrides add growth_rate "" 0.07
--glob` from the shell is a tad awkward but matches Typer's positional model.

**Proposal:** if this turns out clunky in Phase 3 agent flows, we can split
into `model overrides add-row` / `add-glob`. Holding off until pain shows up.

## 25. Public surface re-exports `dataset` and `xl` as modules [decision]

`from model import dataset, xl` works (modules), so user code reads:

```python
historical = dataset.csv("inputs/h.csv", index="date")
total = xl.sum(cash_flow[:])
```

Matches the PRD §3.5/§3.6 examples verbatim. No `from model.xl import npv,
sum` shorthand because that conflicts with builtins.

---

## Out of scope for Phase 1 (intentionally — confirming)

These are Phase 2+:

- `model import` / `model export` (Phase 2).
- `@output` for dataset-emitting methods (Phase 2 along with export).
- `model diff`, snapshot tests (Phase 2/3).
- `model agent`, `model doc sync`, `.model/trace` (Phase 3).
- Slicing forms `name[:n]`, `name[n:]` (running windows) — Phase 2.
- Reactive / lazy execution modes (Phase 4).
- Currency / units (PRD §15 open question).

---

## Open follow-ups for Pietro

1. **Layer-2 default rule order**: today the rewriter emits `if t == ...`
   guards top-to-bottom in the order rules are written, with the `n`/`t`
   default rule last. Should we *require* the default rule to be last in
   source, or auto-sort? Auto-sort is implicit magic. Source-order is
   explicit. Phase 1 chose source-order + raise on multiple defaults.
2. **Numeric stability of `xl.npv` etc.**: we use straight `**` exponents.
   For 30+ period horizons this is fine. For monthly NPV over 30 years
   (360 periods), accumulation error is ~1e-12. Worth flagging in Phase 4
   if anyone hits it.
3. **`dataset.csv` type coercion**: `_coerce` tries int → float → str. For
   currencies parsed as 1.10 vs 1.1 this matters. Polars handles this
   better — confirms the §11 pick once we swap.
4. **`overrides.toml` sort/order**: file is appended-then-overwritten, so
   ordering is "last write wins" within a target+period. Should we
   alphabetize on write for diff stability? Phase 1 keeps insertion
   order; cheap to change.
