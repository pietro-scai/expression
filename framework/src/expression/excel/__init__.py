"""``model.excel`` — Excel I/O for the Model DSL (PRD §9, Phase 2).

Public entry points:

- :func:`export` — solve a model and write a ``.xlsx`` mirroring its DAG.
- :func:`verify` — re-read the written workbook, evaluate the formulas, and
  diff against the in-memory solve.
- :func:`import_xlsx` — parse a workbook into a Layer-1 ``expression.py`` skeleton
  plus a ``expression.md`` with TODOs.

The xlsx layout (Phase 2) is intentionally simple:

::

    A          B       C       D       …
  1 (label)    2024    2025    2026    ← period header row
  2 budget     100     =B2*..  =C2*..  ← row formulas
  3 cogs       =B2*..  …
  …
  globals on the "globals" sheet, one cell per glob, with named ranges.
  datasets on hidden "ds_<name>" sheets.

Round-trip contract: values must match the in-memory solve within ``1e-9``
relative tolerance (PRD §9.2).
"""

from __future__ import annotations

from .export import export
from .import_ import import_xlsx
from .verify import VerifyResult, verify

__all__ = [
    "VerifyResult",
    "export",
    "import_xlsx",
    "verify",
]
