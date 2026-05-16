"""Snapshot management and ``sweet diff`` (Phase 3, PRD §10.2).

A snapshot is a pinned record of a previous solve. ``sweet run`` writes the
*latest* solve to ``outputs/result.json`` on every run; the *committed*
snapshot lives separately at ``.model/snapshot.json`` and is updated only
when the user accepts current results via ``sweet snapshot accept``.

``sweet diff`` reports cell-level differences between the current solve and
the committed snapshot. This is the safety net the iteration loop relies on
(PRD §8.3): every change is reviewed before it's accepted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import Model


def snapshot_path(model_dir: Path) -> Path:
    return model_dir / ".model" / "snapshot.json"


def serialize_cells(model: Model) -> dict[str, Any]:
    """``{"row[period]": value}`` form, matching ``outputs/result.json``."""
    out: dict[str, Any] = {}
    for (row_name, t), value in model.cells().items():
        key = f"{row_name}[{t}]" if t is not None else row_name
        out[key] = value
    return out


def serialize_cells_multi(models: list[Model]) -> dict[str, Any]:
    """Multi-model snapshot: ``{"ModelName.row[period]": value}`` form.

    Prefixes every cell key with the model class name so diffs are
    model-scoped. Single-model callers should use ``serialize_cells()``
    to stay backward-compatible with existing snapshots.
    """
    out: dict[str, Any] = {}
    for model in models:
        prefix = type(model).__name__ + "."
        for k, v in serialize_cells(model).items():
            out[prefix + k] = v
    return out


def write_snapshot(model_dir: Path, cells: dict[str, Any]) -> Path:
    path = snapshot_path(model_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cells, indent=2, default=str, sort_keys=True))
    return path


def read_snapshot(model_dir: Path) -> dict[str, Any] | None:
    path = snapshot_path(model_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text())


@dataclass(frozen=True)
class CellDiff:
    key: str
    before: Any  # None means "added"
    after: Any  # None means "removed"

    @property
    def kind(self) -> str:
        if self.key.startswith("+"):
            return "added"
        if self.key.startswith("-"):
            return "removed"
        return "changed"


@dataclass(frozen=True)
class DiffReport:
    added: list[CellDiff]
    removed: list[CellDiff]
    changed: list[CellDiff]

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def total(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)


def diff_cells(current: dict[str, Any], snapshot: dict[str, Any]) -> DiffReport:
    """Compare two ``{cell_key: value}`` maps. Numeric tolerance is exact.

    Tolerance is intentionally exact — solve is deterministic, and drifting
    by ``1e-15`` is a red flag worth surfacing. If false positives become a
    nuisance, add a ``--tol`` flag at the CLI; don't bury it here.
    """
    keys = set(current) | set(snapshot)
    added: list[CellDiff] = []
    removed: list[CellDiff] = []
    changed: list[CellDiff] = []
    for k in sorted(keys):
        if k not in snapshot:
            added.append(CellDiff(k, before=None, after=current[k]))
        elif k not in current:
            removed.append(CellDiff(k, before=snapshot[k], after=None))
        elif current[k] != snapshot[k]:
            changed.append(CellDiff(k, before=snapshot[k], after=current[k]))
    return DiffReport(added=added, removed=removed, changed=changed)


def format_diff(report: DiffReport, max_per_section: int = 50) -> str:
    if report.empty:
        return "(no diff vs snapshot)"
    lines: list[str] = []
    for section, items, marker in (
        ("changed", report.changed, "~"),
        ("added", report.added, "+"),
        ("removed", report.removed, "-"),
    ):
        if not items:
            continue
        lines.append(f"# {section} ({len(items)})")
        for d in items[:max_per_section]:
            if section == "changed":
                lines.append(f"  {marker} {d.key}: {d.before!r} → {d.after!r}")
            elif section == "added":
                lines.append(f"  {marker} {d.key} = {d.after!r}")
            else:
                lines.append(f"  {marker} {d.key} (was {d.before!r})")
        if len(items) > max_per_section:
            lines.append(f"  … {len(items) - max_per_section} more")
    return "\n".join(lines)
