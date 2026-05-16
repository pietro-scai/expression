# Phase 0 — Proposed changes / clarifications to SPECIFICATION.md

This doc records places where Phase 0 implementation had to make a call that
the PRD didn't pin down, plus genuine deviations the spec should ratify or
push back on. Nothing here should change the *behavior* the PRD promises — the
goal is to surface decisions before they harden.

> Status legend: **[decision]** = chose one path; **[deviation]** = differs
> from PRD as written; **[question]** = needs your call.

---

## 1. Layer 1 row signature: `def name(self, t)` [decision]

The PRD shows two row signatures:

- §3.2 (Layer 1, single dim): `def budget(self, t)` — takes `self` + period
- §3.4 (multi-dim, Layer 1-ish): `def revenue(p, r, t)` — *no* `self`

Phase 0 only ships single-dim rows, so I went with `def name(self, t)`. When
multi-dim arrives in Phase 1, we'll need to reconcile. Two paths:

a) Keep `self` for everything: `def revenue(self, p, r, t)`.
b) Drop `self` always, inject scope via the AST sugar (Layer 2). Requires the
   sugar layer to magic in `self.` for every Model attribute access, which is
   already in the plan.

**Proposal:** keep `(self, ...)` in Layer 1; the Layer-2 sugar is what makes
`self` disappear in §3.4 / §3.5 examples. Update §3.4 example to read
`def revenue(self, p, r, t):`.

## 2. `time` is a property on the Model base class [decision]

PRD examples access the period axis as `self.time.first`. This implies `time`
is a fixed attribute name. I implemented it as a property on `Model` that
returns the *single* declared `Periods` instance regardless of the attribute
name the user picks. So `time = periods(2024, 2028)` works, but so does
`years = periods(2024, 2028)` — `self.time` finds it.

**Proposal:** document that `self.time` always points to the single period
axis in v1, and that the attribute *name* is conventionally `time`. Multiple
period axes are out of scope for v1.

## 3. `Glob` exposed as a descriptor (transparent value access) [decision]

`growth_rate = glob(0.05)` followed by `self.growth_rate` returns the value
(not the `Glob` wrapper). Implemented as a data descriptor with `__set__`
support so users can do `m.growth_rate = 0.20` to override at the instance
level — that override sticks across `solve()` calls. This is a low-cost
enabler for parameter sweeps that should help Phase 4 work.

**Proposal:** add a sentence to §3 explicitly stating that globals are
plain-value attributes at runtime, and that instance-level assignment
overrides the default.

## 4. Recursive self-reference is not a circular dependency [decision]

`self.budget(t-1)` inside `budget()` is the canonical lag pattern; it's not a
DAG cycle, only a temporal one. The implementation:

- Builds the inter-row DAG via AST analysis, **excluding self-references**.
- At evaluation time, periods are computed in order; `self.budget(t-1)` hits
  the cell cache populated by the previous iteration.
- A genuine in-period self-cycle (e.g. `return self.x(t) + 1`) is detected at
  runtime via a `_computing` set and raises `CircularReferenceError`.

This matches PRD intent (§4.2 + §1 "must be a DAG"), but the PRD doesn't
spell out the distinction between *temporal* and *structural* recursion.

**Proposal:** add a short paragraph in §3.2 calling out that `self.row(t-k)`
for `k >= 1` is a lag (always allowed), and `self.row(t)` from the same row
or a structural cycle between rows is the disallowed case.

## 5. Console-script invocation is mandatory; `python -m model.cli` is broken [deviation, important]

When the user is inside the model folder, `cwd/model.py` shadows the
top-level `model` package on `sys.path`, so `python -m model.cli` imports the
*user's* `model.py` and fails. The installed `model` console script does
not put cwd on `sys.path`, so it works.

This is a real footgun of the package-name choice. Options:

a) Document it. CLI is `model`, period; tests + docs use the entry point.
   This is what Phase 0 currently does.
b) Rename the package (e.g. `model_dsl` or `xlmodel`) so the import becomes
   `from model_dsl import Model`. Breaks PRD §3 examples cosmetically.
c) Defensive `sys.path` cleanup inside our CLI.

**Recommendation:** (a) for now. If Phase 1 user-facing breakage shows up,
revisit (c).

## 6. Pyright strict mode relaxes networkx generics [deviation]

§11 says "pyright strict". Strict mode flags every `networkx.DiGraph` use
because the upstream stubs leave the generic parameter as `Unknown`. Phase 0
config keeps strict mode but disables the five `reportUnknown*` /
`reportMissingTypeArgument` rules globally. Our own code is still under all
other strict checks (e.g. `reportPrivateUsage`, missing returns, etc.).

**Proposal:** add a footnote to §11 acknowledging this. Alternatively, we
write our own minimal stubs file for the networkx subset we actually use.

## 7. CLI surface: argument quoting for `model show 'budget[2024]'` [decision]

`[`/`]` are shell glob chars. The CLI accepts the bracketed form and we tell
users to quote it; it also accepts the period as nothing-fancy (just the row
name) and prints the whole series. We did *not* add a `--period`/`-p` flag
because the bracketed form is the documented shape (§7) and adding a second
spelling now would be premature.

## 8. Output format for `outputs/result.json` [decision]

PRD says "writes outputs/result.json" (§5) but doesn't pin format. Chose
flat string keys: `{"budget[2024]": 100.0, "budget[2025]": 105.0, ...}`. This
is git-diff friendly and keeps the file readable. Snapshot tests in Phase 1
will benefit from a stable, sorted order — currently insertion order, which
matches topological + period order (deterministic given the inputs).

**Proposal:** call out the format in §10.2 once snapshot tests land. If
`deepdiff` (§11) is the diff tool, a nested dict structure
(`{"budget": {"2024": ..., "2025": ...}}`) might give nicer diffs. Easy to
swap later — the format is internal.

## 9. `model init` template content [decision]

PRD §7 says "Create a new model folder" but doesn't specify the template.
Phase 0 `model init <name>` creates:

```
<name>/
├── model.py        # a working Layer-1 Budget model (PRD example 12.1)
├── model.md        # PRD §6 skeleton with Purpose / Inputs / Outputs / ...
├── inputs/         # empty
├── outputs/        # empty
└── tests/          # empty
```

No `overrides.toml` (Phase 1), no `.model/` (Phase 3 trace dir). The
generated `model.py` is in Layer-1 form, since Layer-2 sugar is Phase 1.

## 10. `__init_subclass__` inheritance for rows / globs / periods [decision]

A subclass `class B(Budget)` inherits `Budget`'s rows, globs, and periods.
Subclass attributes shadow same-named parent attributes. The PRD doesn't
mention model inheritance; this fell out of the implementation cheaply. Worth
a line in the docs once Phase 1 covers `depends()` (which is the *main*
composition mechanism per §3.8).

## 11. Errors are wrapped in `ModelError` [decision]

`Model.solve()` re-raises domain errors as `ModelError` and wraps unexpected
exceptions raised inside row bodies with the offending `(row, period)`
context. That makes the PRD §12.5 `model show` UX possible without further
plumbing. `CircularReferenceError` extends `ModelError`.

**Proposal:** add `ModelError` to the public surface; agents should
`except ModelError` rather than bare `Exception`.

---

## Out of scope for Phase 0 (already in PRD plan, just confirming)

The following are intentionally *not* implemented yet — confirming they
remain Phase 1+:

- Layer 2 AST sugar (`budget[first] = ...`, `budget[n-1]`).
- `dim()`, `matrix()`, `@row(over=[...])` multi-dim rows.
- `@scalar` rows + `xl.*` namespace.
- `dataset.csv()`, `dataset.from_row()`.
- `depends()` cross-model composition.
- `overrides.toml` and `model overrides` subcommands.
- `model import`, `model export`, `model explain`, `model diff`, `model test`,
  `model doc sync`, `model agent`.

If any of those are needed earlier, that's a scope change to discuss.
