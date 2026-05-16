---
name: excel-fidelity
description: sweet export must round-trip. If verification fails, surface the diff, don't paper over it.
---

`sweet export` runs a verification step (PRD §9.2): the exported `.xlsx` is
re-evaluated and diffed against the in-memory solve. If it fails:

1. Show the user the first 10 mismatched cells **as reported by the CLI**.
2. Investigate root cause — usually a formula generator missing an Excel
   function, or a precision mismatch.
3. Fix the underlying generator/evaluator, not the formula in the workbook.
4. Re-run `sweet export`. Only declare success when verification passes.

Do NOT pass `--skip-verify` to make the error go away. Drift in exports
breaks the contract that lets users hand workbooks to non-`model` colleagues.
