---
name: import-excel
description: Restructure aggressively when importing. Don't transliterate Excel.
---

When the user runs `sweet import some.xlsx`, the CLI produces a Layer-1
skeleton. Your job is **not** to make the model.py mirror the workbook
cell-by-cell — it's to produce a *cleaner* model than the original Excel.

- Identify the time axis (usually a year header row). Make it `periods(...)`.
- Identify dimension axes (product lists, region lists). Make them `dim(...)`
  and use `@row(over=[...])` for rows that vary across those axes. Bare
  `@row` is only for one-dimensional time rows.
- Globals (single named cells used in many formulas) become `glob(...)` with
  a `doc=` string lifted from the surrounding label cell.
- Hardcoded one-off values in formulas → recorded overrides
  (`override-discipline` skill).
- Anything ambiguous goes into `model.md` under "Issues found" — confirm
  with the user before guessing.
- Avoid adding optional heavy imports such as SciPy to generated formulas
  unless the workspace explicitly installs them. Prefer small stdlib helpers
  for examples like IRR/root finding.

The auto-generated `tests/test_excel_roundtrip.py` is the safety net: every
original cell value must match the solved value within `1e-9`. The import
isn't done until that test is green.
