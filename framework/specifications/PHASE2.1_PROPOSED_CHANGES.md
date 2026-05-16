# Phase 3 — Proposed changes / clarifications to SPECIFICATION.md

Same convention as Phase 0/1/2 docs: surface the design calls Phase 3
implementation made where the PRD didn't pin them down.

This slice of Phase 3 ships **display primitives** — pretty-printing
the solved model at the CLI. Other Phase-3 work (interactive importer
agent loop, formula re-derivation, `model diff` / snapshots, scalar
formula export) remains open and proceeds separately.

> Status legend: **[decision]** = chose one path; **[deviation]** =
> differs from PRD as written; **[question]** = needs your call.

Builds on Phase 0 (#1-11), Phase 1 (#12-25), Phase 2 (#26-40). Numbers
continue from there.

---

## 41. `model print` is a separate command, not `show --all` [decision]

PRD §7 lists `model show <cell|row>` for inspecting one target.
Adding "print everything" as `show --all` would overload `show` with
two distinct mental models (one cell vs whole sheet). Phase 3 ships a
new top-level command, `model print`, that always solves and prints
the model in full — single responsibility, terse to type.

`show` keeps its existing shape (one row or one cell, with period
axis).

**Proposal:** §7 add `model print [--format table|csv]` to the CLI
command list.

## 42. Default output is text table; CSV is opt-in [decision]

`model print` defaults to a column-aligned text table: human-readable
at the terminal, copy-pasteable into a markdown doc. CSV is opt-in
via `--format csv` for piping into spreadsheets, `column -ts,`, or
scripts.

JSON is *not* added — `model run` already writes
`outputs/result.json`, so machine-readable output exists in tree form
already. Adding a third format would be feature creep without a use
case.

Rationale for table-as-default: the next-up interactive surface (a
REPL/agent loop) renders text natively; a default that humans read at
a glance is the right primitive to build on.

## 43. Single periods axis only — multi-dim rows deferred [decision]

The formatter assumes one `periods(...)` axis (matches Phase 0/1
constraints). `format_table()` / `format_csv()` raise `ModelError` if
zero or multiple `periods(...)` axes are present.

Multi-dim rows (`@row(over=[products, regions, time])`) require a
pivot decision — see Phase 2 follow-up #3 ("should `revenue[p, r, t]`
write as one row per `(p, r)` with period columns, wide grid, or
pivot-table-style?"). The same question applies to display; deferring
both to a later phase keeps the decision aligned across export and
print.

## 44. Scalars rendered as a trailing block, separated by blank line [decision]

After the period table, scalars (if any) appear as `name = value`
lines, separated from the row grid by a blank line.

Reasoning: scalars don't have a period column to align under;
embedding them in the main grid would require an em-dash placeholder
per period and visually misleads the reader into expecting a series.
A trailing block is the simplest format that keeps the two concepts
visually distinct.

CSV mirrors this: rows first (with period header), blank line, then
`name,value` pairs for each scalar.

## 45. Float formatting: int-collapse + `%.6g` [decision]

`100.0` prints as `100`, `1.5` as `1.5`, `1.5e-09` as `1.5e-09`.
Algorithm:
- Floats that equal their `int()` (and aren't huge) collapse to the
  int form. Avoids visual noise on round numbers.
- Otherwise `%.6g` — keeps wide-range numbers readable without
  forcing a fixed decimal count.

Six significant figures is enough for terminal display; users wanting
more precision should use `--format csv` (which emits Python's `repr`
of each value via the `csv` module) or read `result.json` directly.

## 46. `Model.__str__` returns the table; `__repr__` stays terse [decision]

`print(m)` after `solve()` prints the full table — convenient for
REPL / notebook use, and matches how built-in containers behave under
`print`. Before solve, `str(m)` returns `<Demo: not solved>` so
accidentally printing an unsolved model doesn't raise: raising from
`__str__` violates the principle of least surprise — `print(m)` is
too low-stakes a call.

`repr(m)` is always short and structural:
`<Demo: 1 row, 5 cells, solved>`. Use `format_table()` directly when
you want the table independent of `__str__`'s solved-vs-not branching.

**Proposal:** §3 mention that `Model` has a default text
representation suitable for REPL use; the CLI wraps it.

## 47. `model run` output unchanged [decision]

Tempting to refactor `run` to use `format_table()` so the two commands
agree. Resisted: `run` reports a *solve operation* (status lines +
inline series + writes `result.json`); `print` is a *viewer* over the
solved state. They have different jobs and different audiences (CI
pipeline vs terminal user). Keeping them separate also means changing
the table layout doesn't churn `run`'s acceptance tests.

If a future flag like `model run --print-table` lands, it composes
the two without coupling them.

---

## Out of scope for this Phase 3 slice (intentionally)

- Multi-dim row rendering (paired with the pivot decision in §43).
- Color / TTY detection / Rich library (extreme simplicity per §1).
- `model diff` / snapshot view (separate Phase 3 work — see PRD §6).
- HTML / Markdown table formats (no driver use case yet).
- Globals block in the table (they're inputs, not solved output —
  surface via `model show <glob>` or read `model.py` directly).
- Refactoring `model run` to share the formatter (#47 above).

---

## Open follow-ups for Pietro

1. **Truncation for wide period axes.** A 30-year model produces a
   table wider than most terminals. Options: (a) wrap, (b) page,
   (c) print-only-N-with-`--periods 2024:2030`. Defer until someone
   hits it; for now, redirect to CSV.
2. **Sparkline column.** A tiny inline trend (`▁▂▃▅▇`) per row would
   make the table much more glance-able. Cute but extra dep on
   Unicode rendering. Worth a flag (`--sparkline`) once the CLI gets
   more formatting work.
3. **Formatter override per-row.** `glob(0.05, format=".1%")` so a
   percentage glob renders as `5.0%`. The current `Glob` class
   already accepts `doc=` — adding `format=` is mechanical but adds
   surface area. Wait until a model hits readability pain.
