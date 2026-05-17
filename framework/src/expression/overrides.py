"""``overrides.toml`` loading + application (PRD §3.7).

Overrides are *recorded data*, never edited into formulas. Format:

.. code-block:: toml

    [[override]]
    row = "revenue"
    period = 2025
    value = 1500
    reason = "New customer signed Q1 2025"
    author = "pietro"

Globals can also be overridden::

    [[override]]
    glob = "growth_rate"
    value = 0.07
    reason = "Updated forecast"

At solve time, row/period overrides are pre-populated into ``model._cells``
*before* topological evaluation. Because :class:`~model.core.BoundRow` checks
the cache first, downstream rows see the overridden value naturally.
Glob overrides are applied via the same instance-level ``__set__`` mechanism
Phase 0 already supports.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import Model, ModelError


@dataclass(frozen=True)
class Override:
    """A single override entry."""

    target: str  # row name or glob name
    value: Any
    period: Any | None = None  # None for globs / scalar rows
    reason: str = ""
    author: str = ""
    kind: str = "row"  # "row" or "glob"
    model: str | None = None  # optional: restrict to a specific Model class name

    def to_toml_table(self) -> dict[str, Any]:
        out: dict[str, Any] = {"value": self.value}
        if self.kind == "glob":
            out["glob"] = self.target
        else:
            out["row"] = self.target
            if self.period is not None:
                out["period"] = self.period
        if self.reason:
            out["reason"] = self.reason
        if self.author:
            out["author"] = self.author
        if self.model:
            out["model"] = self.model
        return out


def read_overrides(path: Path) -> list[Override]:
    """Read ``overrides.toml``. Returns ``[]`` if the file does not exist."""
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text())
    raw = data.get("override", [])
    if not isinstance(raw, list):
        raise ModelError(f"{path}: expected [[override]] tables, got {type(raw).__name__}")
    out: list[Override] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ModelError(f"{path}: override #{i} is not a table")
        if "glob" in item:
            out.append(
                Override(
                    target=item["glob"],
                    value=item["value"],
                    reason=item.get("reason", ""),
                    author=item.get("author", ""),
                    kind="glob",
                )
            )
        else:
            target = item.get("row")
            if target is None:
                raise ModelError(f"{path}: override #{i} must specify 'row' or 'glob'")
            out.append(
                Override(
                    target=target,
                    period=item.get("period"),
                    value=item["value"],
                    reason=item.get("reason", ""),
                    author=item.get("author", ""),
                    kind="row",
                    model=item.get("model"),
                )
            )
    return out


def _format_value(v: Any) -> str:
    if isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    return repr(v)


def write_overrides(path: Path, overrides: list[Override]) -> None:
    """Write overrides as a TOML file (minimal, hand-written for readability)."""
    lines: list[str] = []
    for ov in overrides:
        lines.append("[[override]]")
        if ov.kind == "glob":
            lines.append(f'glob = "{ov.target}"')
        else:
            lines.append(f'row = "{ov.target}"')
            if ov.period is not None:
                lines.append(f"period = {_format_value(ov.period)}")
        lines.append(f"value = {_format_value(ov.value)}")
        if ov.reason:
            lines.append(f"reason = {_format_value(ov.reason)}")
        if ov.author:
            lines.append(f"author = {_format_value(ov.author)}")
        if ov.model:
            lines.append(f"model = {_format_value(ov.model)}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n" if lines else "")


def apply_overrides(model: Model, overrides: list[Override]) -> None:
    """Apply overrides to ``model`` *before* solving.

    Glob overrides set the instance attribute (Phase 0 descriptor pattern).
    Row overrides pre-populate the cell cache so downstream cells see them.
    """
    rows = model._rows  # pyright: ignore[reportPrivateUsage]
    scalars = model._scalars  # pyright: ignore[reportPrivateUsage]
    globs = model._globs  # pyright: ignore[reportPrivateUsage]
    cells: dict[tuple[str, Any], Any] = model._cells  # pyright: ignore[reportPrivateUsage]

    for ov in overrides:
        if ov.kind == "glob":
            if ov.target not in globs:
                raise ModelError(f"Override target {ov.target!r} is not a glob on this model")
            setattr(model, ov.target, ov.value)
            continue
        # row / scalar override
        if ov.target in scalars:
            if ov.period is not None:
                raise ModelError(
                    f"Override for scalar {ov.target!r} must not specify a period"
                )
            cells[(ov.target, None)] = ov.value
            continue
        if ov.target not in rows:
            raise ModelError(f"Override target {ov.target!r} is not a row on this model")
        if ov.period is None:
            raise ModelError(
                f"Override for row {ov.target!r} must specify 'period' (or use a scalar)"
            )
        cells[(ov.target, ov.period)] = ov.value


def solve_with_overrides(model: Model, overrides_path: Path | None = None) -> Model:
    """Convenience: apply overrides from ``overrides.toml`` (if any), then solve."""
    if overrides_path is not None:
        overrides = read_overrides(overrides_path)
        apply_overrides(model, overrides)
    model.solve()
    return model
