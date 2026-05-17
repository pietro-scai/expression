"""``dataset`` — input/output tabular data (PRD §3.6).

Phase 1 ships a stdlib-based implementation. Polars (per PRD §11) is a future
swap that doesn't change the public API:

- :func:`csv` — read a CSV as a class-level model attribute.
- :func:`from_row` — produce a Dataset from a solved row's series (for export).

The descriptor pattern matches Glob/Matrix: ``self.historical`` returns a live
:class:`Dataset` object on the model instance.
"""

from __future__ import annotations

import csv as _csv
from pathlib import Path
from typing import Any

from .core import Model, ModelError


class Dataset:
    """An in-memory table with named columns and an optional index column."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        index: str | None = None,
    ) -> None:
        self.rows = rows
        self.index = index

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    @property
    def columns(self) -> list[str]:
        return list(self.rows[0].keys()) if self.rows else []

    def last(self, col: str) -> Any:
        """Return the value in the last row's ``col`` column."""
        if not self.rows:
            raise ModelError("dataset is empty")
        if col not in self.rows[-1]:
            raise ModelError(f"column {col!r} not in dataset; have {self.columns}")
        return self.rows[-1][col]

    def first(self, col: str) -> Any:
        if not self.rows:
            raise ModelError("dataset is empty")
        return self.rows[0][col]

    def lookup(self, key: Any, col: str) -> Any:
        """Find the row whose index column equals ``key`` and return ``col``."""
        if self.index is None:
            raise ModelError("lookup requires an index column")
        for r in self.rows:
            if r[self.index] == key:
                return r[col]
        raise KeyError(f"key {key!r} not found in column {self.index!r}")

    def column(self, col: str) -> list[Any]:
        """Return all values in ``col`` (in row order)."""
        return [r[col] for r in self.rows]


class _CsvDescriptor:
    """Class-level descriptor for ``dataset.csv(...)``.

    Lazily reads and parses the CSV on first access, then caches per instance.
    """

    def __init__(self, path: str | Path, index: str | None = None) -> None:
        self.path = Path(path)
        self.index = index
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        cache: dict[str, Dataset] = obj.__dict__.setdefault("_dataset_cache", {})
        if self._name in cache:
            return cache[self._name]
        ds = self._load()
        cache[self._name] = ds
        return ds

    def _load(self) -> Dataset:
        if not self.path.exists():
            raise ModelError(f"CSV not found: {self.path}")
        with self.path.open(newline="") as f:
            reader = _csv.DictReader(f)
            rows = [{k: _coerce(v) for k, v in r.items()} for r in reader]
        if self.index is not None and rows and self.index not in rows[0]:
            raise ModelError(
                f"{self.path}: index column {self.index!r} not in CSV columns "
                f"{list(rows[0].keys())}"
            )
        return Dataset(rows=rows, index=self.index)


def _coerce(s: Any) -> Any:
    """Best-effort coerce string CSV cells to int/float/str."""
    if not isinstance(s, str):
        return s
    if s == "":
        return None
    try:
        i = int(s)
        if str(i) == s:
            return i
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def csv(path: str | Path, index: str | None = None) -> Any:
    """Read a CSV file as a model attribute (PRD §3.6).

    Usage::

        class Forecast(Model):
            historical = dataset.csv("inputs/historical.csv", index="date")
    """
    return _CsvDescriptor(path, index=index)


def from_row(model: Model, row_name: str, columns: list[str] | None = None) -> Dataset:
    """Build a Dataset from a *solved* row's series (PRD §3.6).

    For a single-axis row over ``time``, produces rows with columns
    ``[<period_label>, <row_name>]`` (default), or the supplied ``columns``
    pair ``["year", "revenue"]`` etc.
    """
    if row_name not in model._rows:  # pyright: ignore[reportPrivateUsage]
        raise ModelError(f"Unknown row: {row_name}")
    period_col, value_col = (columns or ["period", row_name])
    rows: list[dict[str, Any]] = [
        {period_col: t, value_col: model.cell(row_name, t)} for t in model.time
    ]
    return Dataset(rows=rows, index=period_col)
