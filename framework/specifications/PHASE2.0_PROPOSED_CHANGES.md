# Phase 2 — Proposed changes / clarifications to SPECIFICATION.md

Same convention as the Phase 0/1 docs: surface the design calls Phase 2
implementation made where the PRD didn't pin them down.

> Status legend: **[decision]** = chose one path; **[deviation]** = differs
> from PRD as written; **[question]** = needs your call.

Builds on Phase 0 (#1-11) and Phase 1 (#12-25). Numbers continue from there.

---

## 26. Workbook layout: row-per-row, sheet-per-concern [decision]

PRD §9.2 mandates "header (period or dimension labels) and a formula per
cell" but doesn't pin down sheet structure. Phase 2 layout:

| Sheet | Contents |
|---|---|
| `model` | one row per `@row`, columns = periods (header in row 1, A1=label) |
| `globals` | one row per `glob`; B-column cells are workbook-named ranges |
| `scalars` | one row per `@scalar` (Phase 2 stores the *value* — see §28) |
| `ds_<name>` | hidden sheet per `dataset.csv` attribute, header + data rows |

Rationale: trivially diff-able, each concern lives in its own sheet so users
can edit globals without touching formulas. The `globals` sheet means a
formula like `=B2*(1+growth_rate)` references a *named* range, never a raw
cell — so renumbering rows doesn't break refs.

**Proposal:** standardize this in §9.2.

## 27. Cell refs: relative-col + absolute-row for cross-row, all-relative for self [decision]

When emitting `self.budget(t-1)` from inside `budget`'s row, we use a
relative ref like `B2`. When emitting `self.cogs(t)` from inside
`gross_profit`, we use `B$2` (relative col + absolute row).

This means:
- Self-references slide naturally column-to-column (the lag pattern works
  when the column moves).
- Cross-row references nail the row but track the period column.

Without this distinction, copy-paste in Excel would break formulas. **Worth
calling out in §9.2** because it shapes how a human-edited workbook can be
re-imported.

## 28. Scalars exported as constants in Phase 2 [deviation]

PRD §3.5 says scalars "round-trip to Excel as a single named cell." Phase 2
writes the *computed value* into `scalars!B<i>` and points a named range at
it. We do **not** yet emit Excel-formula equivalents for scalars (the body
often contains `xl.npv`, `xl.irr` calls that map to Excel `NPV`, `IRR` —
straightforward — but also custom-registered functions and bespoke loops
that don't have an Excel analog).

Round-trip values are correct; round-trip *formulas* for scalars land in
Phase 3 alongside `model export --excel-formulas` work.

**Proposal:** add a sentence in §3.5 that Phase-2 export pins scalar values;
Phase-3 will emit native Excel formulas where the function maps cleanly.

## 29. UnsupportedFormula → value fallback (with cell comment) [decision]

`_formula.row_formula_for_period` raises `UnsupportedFormula` when the body
uses constructs the renderer can't translate (e.g., user-defined helper
calls, `xl.*` functions outside a small whitelist, list comprehensions).
The exporter catches it and writes the *value* with a comment like
`"value (formula unsupported in export)"`. The verifier still passes
because it diffs values, not formulas — but the produced workbook is
"frozen" in those cells: editing inputs in Excel won't propagate.

This is a **better-than-failing** stance, matching the PRD's "round-trip
fidelity contract: values must match within tolerance" (§9.2) without
gating on formula coverage.

**Proposal:** call this out in §9.2 as the fallback contract; agents can
flag affected cells via the comment.

## 30. Verifier: built-in fallback evaluator [deviation]

PRD §11 specifies the `formulas` library for round-trip verification.
Installing `formulas` pulls in numpy, sympy, openpyxl, et al. — heavy. We
keep `formulas` as an *optional* extra (`pip install model[verify]`) and
ship a small fallback evaluator covering the dialect we *emit*: numbers,
strings, `+ - * / ^`, comparisons, `IF` / `AND` / `OR` / `NOT` / `MOD` /
`INT` / `SUM` / `AVERAGE` / `MIN` / `MAX`, named ranges, ranges.

If `formulas` is installed it wins automatically (`_make_evaluator`
prefers it). This means:

- Phase 2 acceptance test ("round-trips that model with all values matching
  to 1e-9", §16 success criteria) doesn't pull a heavy dep tree.
- Third-party workbooks with `VLOOKUP`, `XIRR`, etc. still need
  `formulas` for verification — flagged as a future install hint.

**Proposal:** add to §11 that `formulas` is optional; the package ships its
own evaluator for self-emitted workbooks.

## 31. Importer: non-interactive in Phase 2 [decision]

PRD §9.1 step 4 says the agent "presents its interpretation row-by-row and
asks for confirmation." Phase 2 ships the *parser* and the *renderer* but
no interactive agent loop — that's Phase 3. The non-interactive flow:

1. Detect time axis (consecutive integers in row 1).
2. Detect globals from named-range definitions.
3. For each row in the `model` sheet, encode the *values* as per-period
   `if/elif` branches in a Layer-1 method. Original formulas are discarded
   (preserved as comments where present).
4. Emit a `model.md` with TODOs flagging issues + asking the user/agent to
   replace the value-encoded bodies with proper formulas.

This guarantees `model run` after import reproduces every cell value of
the source — honoring the §9.1 step-6 invariant. Re-deriving formulas
*correctly* is the hard part and gets the agent treatment in Phase 3.

**Proposal:** §9.1 should split "import" into "import-skeleton" (Phase 2)
and "import-with-agent" (Phase 3). Both have value: the skeleton is a
useful artifact even without further refinement.

## 32. Importer: `_slugify()` for non-identifier labels [decision]

Excel row labels like `"Gross Profit ($K)"` aren't valid Python identifiers.
We slugify to `"gross_profit_k"` and record the rename in the `Issues
found` section of `model.md`. A label whose slug starts with a digit gets
prefixed with `row_`.

**Proposal:** §9.1 acknowledge the slug step; users who want the label
preserved as Excel-side metadata can add a `# label: "Gross Profit ($K)"`
comment that the agent uses on round-trip.

## 33. `model export` is `model.xlsx` by default [decision]

PRD §7 shows `model export [--out file.xlsx]` (default not specified).
Phase 2 default: `outputs/model.xlsx` relative to the model.py folder.
Matches the §5 layout (outputs/ holds produced artifacts) and
result.json's neighborhood.

## 34. Verification mismatches surface only the first 10 [decision]

PRD §9.2 step 7 says "errors with the first 10 mismatched cells." Phase 2
implements that exactly via `VerifyResult.first_mismatches(10)`. The full
mismatch list is preserved on the result object for programmatic callers.

## 35. `formulas` library wrapper unwraps result types [decision]

`formulas` returns numpy/Sympy values. Verifier comparison is against
plain Python ints/floats from the in-memory solve. We unwrap via `.item()`
when present. The wrapper is in `verify._unbox` — small and isolated so
it's easy to swap if a future `formulas` update changes shapes.

## 36. Datasets exported as hidden sheets [decision]

PRD §9.2 step 4: "Datasets become hidden sheets." Phase 2 implements
this as `ds_<attribute_name>` (e.g. `ds_historical`) with the dataset's
columns as header row + data rows. Since the dataset isn't referenced by
exported formulas in Phase 2 (datasets feed *Python* logic in the row body,
which we currently can't translate to Excel), the hidden sheet is
essentially a record of what the model loaded — useful for audit and Phase
3 importer round-trips.

**Proposal:** §9.2 add: "Datasets are written as hidden sheets so a future
agent can re-import without re-attaching the source CSV."

## 37. Overrides exported as hardcoded cells with comments [decision]

PRD §9.2 step 5 specifies "Overrides become hardcoded values with a
comment cell explaining the override reason." Phase 2 plumbs this via
`model._exported_overrides: dict[(row, period), reason]` — the
`apply_overrides` flow doesn't currently keep that metadata around, so
callers who want comments must populate the dict themselves before
calling `export`. Default behavior: overrides are written as values
(round-trip-correct) without a "this was an override" comment.

**Proposal:** Phase 3 should refactor `apply_overrides` to record
`(row, period) → Override` on the model so the export step picks it up
automatically. The plumbing is wired; the data flow is missing.

## 38. Period type is `int` only in Phase 2 [decision]

Both export and import assume integer year periods. `Periods(2024, 2028)`
fits this. Date / month / quarter periods are deferred — they'd require
date-aware column headers and a richer guard expression in
`_select_branch_for_period` (currently checks `period == const_int`).

**Proposal:** §3.3 clarify that periods are integer years for v1; richer
period types are a Phase 4 candidate alongside the units / currency
question (Phase 1 doc §3 / PRD §15 #1).

## 39. ``model import`` doesn't yet call out to `formulas` for parsing [decision]

PRD §9.1 step 3: "Each formula row is parsed (use `formulas` library or
`xlcalculator`) into an AST." Phase 2 reads cells via openpyxl's
`data_only=True`, which gives us *values* but loses formulas. So we encode
values, not formulas — leaving the formula-AST work for Phase 3 (where it
goes hand in hand with the agent loop).

The Phase-2 importer is therefore "lossy on formulas, lossless on values."
That's a deliberate tradeoff to ship a usable import path now.

**Proposal:** §9.1 split clearly: Phase 2 = value-faithful skeleton, Phase
3 = formula-faithful + agent confirmation.

## 40. Pyright: optional `formulas` import is `# type: ignore` [decision]

We don't add `formulas` to dev deps because it's heavy. Pyright would
otherwise error on the import — silenced with `# type: ignore`. When a
user opts into `pip install model[verify]`, the import resolves fine and
the wrapper kicks in.

---

## Out of scope for Phase 2 (intentionally)

- Interactive agent flow during import (Phase 3).
- Formula-faithful re-derivation on import (Phase 3).
- Excel-formula form for `@scalar` (Phase 3 — needs `xl.*` → Excel mapping).
- Snapshot tests / `model diff` (Phase 3).
- Multi-dim row export — current export handles 1-D rows; multi-dim would
  need a different sheet shape (one row per index combination, or a
  per-axis pivot). Track separately.
- Date / fractional / quarterly periods (Phase 4, see §38).
- `model.md` reconciliation on `model run` (Phase 3, PRD §6).

---

## Open follow-ups for Pietro

1. **Reimporting our own export**: an `export` followed by `import` is
   currently lossy (the importer sees per-period values, not the original
   formula). We could preserve the formula source by stashing the Python
   row body as a workbook-level comment or doc-property. Worth the
   complexity? My lean: defer to Phase 3 — formula re-derivation should be
   agent-driven anyway.
2. **Dataset round-trip on import**: a Phase-3 importer reading `ds_*`
   hidden sheets back into `dataset.csv()` calls would be nice. Today
   they're write-only on export, ignored on import.
3. **Multi-dim export shape**: should `revenue[p, r, t]` write as
   (a) one row per `(p, r)` with period columns, (b) wide grid with both
   row and column headers, or (c) pivot-table-style? Different consumers
   want different shapes. Don't pick before someone asks.
4. **`model export --excel-formulas`** (Phase 3): a flag that *requires*
   formula success, erroring instead of falling back to values. Useful for
   "this model must round-trip" workflows. Worth it as a CI gate.
