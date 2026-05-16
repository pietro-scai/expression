---
description: Inspect one cell or whole row by name.
---

The user will pass a cell or row reference (e.g. `revenue` or `revenue[2024]`).

1. Run `sweet show '<arg>'` — quote the argument so the shell does not glob
   the brackets.
2. Print the value(s) verbatim.
3. If the user asked "why" or "where does this come from", chain into
   `/sweet:explain` for the same target.
