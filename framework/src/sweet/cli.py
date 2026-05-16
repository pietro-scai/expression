"""CLI for ``model``: ``init``, ``run``, ``show``, ``overrides``."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import networkx as nx
import typer

from .core import Model, ModelError
from .output import describe_models, to_json, to_json_multi
from .overrides import (
    Override,
    apply_overrides,
    read_overrides,
    write_overrides,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="model — Excel-like spreadsheets as Python DAGs.",
)
overrides_app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="Manage overrides.toml."
)
app.add_typer(overrides_app, name="overrides")
snapshot_app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="Manage solve snapshots."
)
app.add_typer(snapshot_app, name="snapshot")
doc_app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="Reconcile sweet.md with sweet.py."
)
app.add_typer(doc_app, name="doc")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_module(model_path: Path) -> types.ModuleType:
    """Import ``sweet.py`` and return the loaded module."""
    if not model_path.exists():
        raise typer.BadParameter(f"No sweet.py found at {model_path}")
    spec = importlib.util.spec_from_file_location("user_model", model_path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"Could not load {model_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["user_model"] = module
    # Add the model file's directory so sibling modules can be imported.
    model_dir = str(model_path.parent.resolve())
    if model_dir not in sys.path:
        sys.path.insert(0, model_dir)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _topo_sort_models(classes: list[type[Model]]) -> list[Model]:
    """Build a cross-model DAG from depends() declarations and topo-sort.

    Only edges between models *in the same file* are considered — external
    depends() upstreams are left to each model's own lazy resolution.
    Circular dependencies raise ModelError with the cycle path.
    """
    in_file: dict[str, type[Model]] = {cls.__name__: cls for cls in classes}
    g: nx.DiGraph = nx.DiGraph()
    for cls in classes:
        g.add_node(cls.__name__)
        for dep in cls._depends.values():  # pyright: ignore[reportPrivateUsage]
            upstream_name = dep.upstream.__name__
            if upstream_name in in_file:
                g.add_edge(upstream_name, cls.__name__)

    if not nx.is_directed_acyclic_graph(g):
        cycles = list(nx.simple_cycles(g))
        cycle_str = " ; ".join(" -> ".join([*c, c[0]]) for c in cycles)
        raise ModelError(
            f"Circular dependency between models: {cycle_str}\n"
            "Remove the cycle — models in a circular chain cannot be solved."
        )

    order = list(nx.topological_sort(g))
    return [in_file[n]() for n in order if n in in_file]


def _load_all_models(model_path: Path) -> list[Model]:
    """Load ALL Model subclasses from sweet.py, sorted by cross-model dep order.

    Single-model files take a fast path (no DAG construction needed).
    Multi-model files are topologically sorted by their depends() relationships
    so upstream models are always solved before downstream ones.
    """
    module = _load_module(model_path)
    classes = [
        v
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, Model) and v is not Model
    ]
    if not classes:
        raise typer.BadParameter(f"No Model subclass found in {model_path}")
    if len(classes) == 1:
        return [classes[0]()]
    return _topo_sort_models(classes)


def _load_user_model(model_path: Path) -> Model:
    """Load a single Model — last (root) model in topo order.

    Used by commands that operate on one model at a time (explain, doc sync).
    """
    models = _load_all_models(model_path)
    return models[-1]


_CELL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[([^\]]+)\]$")
_QUALIFIED_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(?:\[([^\]]+)\])?$"
)


def _parse_cell_target(target: str) -> tuple[str, Any | None]:
    """Parse ``budget`` or ``budget[2024]`` into (row, period|None)."""
    match = _CELL_RE.match(target)
    if match:
        row_name, period_str = match.groups()
        try:
            return row_name, int(period_str)
        except ValueError:
            return row_name, period_str
    if "[" in target or "]" in target:
        raise typer.BadParameter(f"Could not parse target: {target!r}")
    return target, None


def _parse_qualified_target(
    target: str,
) -> tuple[str | None, str, Any | None]:
    """Parse ``ModelName.row[period]``, ``row[period]``, or ``row``.

    Returns (model_name_or_None, row_name, period_or_None).
    """
    m = _QUALIFIED_RE.match(target)
    if m:
        model_name, row_name, period_str = m.groups()
        period: Any | None = None
        if period_str is not None:
            try:
                period = int(period_str)
            except ValueError:
                period = period_str
        return model_name, row_name, period
    row_name, period = _parse_cell_target(target)
    return None, row_name, period


def _find_models_with_row(
    models: list[Model], row_name: str, model_name: str | None
) -> list[Model]:
    return [
        m
        for m in models
        if row_name in m.row_names()
        and (model_name is None or type(m).__name__ == model_name)
    ]


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


_INIT_MODEL_PY = '''\
"""Generated by `model init {name}` — Phase 0 (Layer 1)."""

from sweet import Model, glob, periods, row


class {classname}(Model):
    time = periods(2024, 2028)
    seed = glob(100, doc="Starting budget in $K")
    growth_rate = glob(0.05, doc="Annual growth rate")

    @row
    def budget(self, t):
        if t == self.time.first:
            return self.seed
        return self.budget(t - 1) * (1 + self.growth_rate)
'''

_INIT_MODEL_MD = '''\
# {classname} model

## Purpose
One paragraph: what business question does this answer?

## Inputs
- `seed` (global, default 100) — starting budget in $K
- `growth_rate` (global, default 5%) — annual revenue growth

## Outputs
- `budget[year]` — projected annual budget {start}-{end}

## Logic
`budget` grows at `growth_rate` from `seed` each year.

## Known issues / open questions
- [ ] None yet.

## Overrides
None.

## Changelog
- {date}: created via `model init {name}`.
'''


@app.command()
def init(
    name: str = typer.Argument(..., help="Folder name for the new model."),
) -> None:
    """Create a new model folder."""
    from datetime import date

    path = Path(name)
    if path.exists():
        raise typer.BadParameter(f"{path} already exists.")
    classname = "".join(part.capitalize() for part in re.split(r"[_\-\s]+", name)) or "MyModel"
    path.mkdir(parents=True)
    (path / "inputs").mkdir()
    (path / "outputs").mkdir()
    (path / "tests").mkdir()
    (path / "sweet.py").write_text(_INIT_MODEL_PY.format(name=name, classname=classname))
    (path / "sweet.md").write_text(
        _INIT_MODEL_MD.format(
            classname=classname, name=name, start=2024, end=2028, date=date.today().isoformat()
        )
    )
    typer.echo(f"✓ Created model at {path}/")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    mode: str = typer.Option("eager", "--mode", help="Execution mode (only 'eager' in Phase 0)."),
    model_path: Path = typer.Option(
        Path("sweet.py"), "--model", help="Path to the sweet.py file."
    ),
) -> None:
    """Solve all models in sweet.py and write outputs/result.json.

    Discovers every Model subclass in the file, resolves their dependency
    order automatically via depends() declarations, and solves them in
    topological sequence. The combined result is written as
    ``{"models": [...]}`` to ``outputs/result.json``.
    """
    if mode != "eager":
        raise typer.BadParameter(f"Only --mode=eager is supported, got {mode!r}")
    try:
        models = _load_all_models(model_path)
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    if len(models) > 1:
        names = " -> ".join(type(m).__name__ for m in models)
        typer.echo(f"✓ Discovered {len(models)} models: {names}")

    ovs = read_overrides(model_path.parent / "overrides.toml")
    for model in models:
        model_name = type(model).__name__
        model_ovs = [o for o in ovs if o.model is None or o.model == model_name]
        try:
            if model_ovs:
                apply_overrides(model, model_ovs)
            model.solve()
        except ModelError as exc:
            typer.echo(f"✗ {model_name}: {exc}", err=True)
            raise typer.Exit(1) from exc
        n_rows = len(model.row_names())
        n_cells = len(model.cells())
        suffix = f" with {len(model_ovs)} override{'s' if len(model_ovs) != 1 else ''}" if model_ovs else ""
        if len(models) > 1:
            typer.echo(
                f"  ✓ Solved {model_name} ({n_rows} row{'s' if n_rows != 1 else ''}, "
                f"{n_cells} cell{'s' if n_cells != 1 else ''}){suffix}"
            )
        else:
            typer.echo(
                f"✓ DAG validated ({n_rows} row{'s' if n_rows != 1 else ''}, {n_cells} cells)"
            )
            typer.echo(f"✓ Solved{suffix}")
            for row_name in model.row_names():
                values = model.series(row_name)
                typer.echo(f"  {row_name}: {values}")

    out_dir = model_path.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    result_path = out_dir / "result.json"
    result_path.write_text(json.dumps(to_json_multi(models), indent=2, default=str))
    typer.echo(f"✓ Wrote {result_path}")


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@app.command()
def show(
    target: str = typer.Argument(
        ...,
        help=(
            "Cell or row to print. Forms: 'budget', 'budget[2024]', "
            "'ModelName.budget', 'ModelName.budget[2024]'."
        ),
    ),
    model_path: Path = typer.Option(
        Path("sweet.py"), "--model", help="Path to the sweet.py file."
    ),
) -> None:
    """Print one cell or whole row, optionally qualified by model name.

    Note: shells often interpret ``[`` and ``]`` as glob characters; quote the
    argument: ``sweet show 'budget[2024]'``.

    With multiple models in the file you can qualify the row name:
    ``sweet show 'SalaryModel.gross_salary[2025]'``.
    """
    try:
        models = _load_all_models(model_path)
        for model in models:
            model.solve()
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    model_name, row_name, period = _parse_qualified_target(target)
    matching = _find_models_with_row(models, row_name, model_name)

    if not matching:
        if model_name:
            typer.echo(f"✗ Unknown row {row_name!r} in model {model_name!r}", err=True)
        else:
            typer.echo(f"✗ Unknown row {row_name!r} (not found in any model)", err=True)
        raise typer.Exit(1)

    for model in matching:
        prefix = f"{type(model).__name__}." if len(models) > 1 else ""
        if period is None:
            for t in model.time:
                typer.echo(f"{prefix}{row_name}[{t}] = {model.cell(row_name, t)}")
        else:
            if not model.has_cell(row_name, period):
                typer.echo(f"✗ No cell {prefix}{row_name}[{period}]", err=True)
                raise typer.Exit(1)
            typer.echo(f"{prefix}{row_name}[{period}] = {model.cell(row_name, period)}")


# ---------------------------------------------------------------------------
# print (Phase 3)
# ---------------------------------------------------------------------------


@app.command(name="print")
def print_cmd(
    fmt: str = typer.Option(
        "table", "--format", "-f", help="Output format: 'table' (default) or 'csv'."
    ),
    model_path: Path = typer.Option(
        Path("sweet.py"), "--model", help="Path to the sweet.py file."
    ),
) -> None:
    """Solve all models and print them as tables (or CSV)."""
    if fmt not in ("table", "csv"):
        raise typer.BadParameter(f"Unknown format: {fmt!r}. Choose: table, csv.")
    try:
        models = _load_all_models(model_path)
        ovs = read_overrides(model_path.parent / "overrides.toml")
        for model in models:
            model_ovs = [o for o in ovs if o.model is None or o.model == type(model).__name__]
            if model_ovs:
                apply_overrides(model, model_ovs)
            model.solve()
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    for i, model in enumerate(models):
        if len(models) > 1:
            mname = type(model).__name__
            sep = f"── {mname} " + "─" * max(0, 40 - len(mname))
            if i > 0:
                typer.echo("")
            typer.echo(sep)
        if fmt == "csv":
            typer.echo(model.format_csv(), nl=False)
        else:
            typer.echo(model.format_table())


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@app.command(name="export")
def export_cmd(
    out: Path = typer.Option(Path("outputs/model.xlsx"), "--out", help="Output .xlsx path."),
    model_path: Path = typer.Option(Path("sweet.py"), "--model", help="Path to sweet.py."),
    skip_verify: bool = typer.Option(
        False, "--skip-verify", help="Skip the round-trip verification step."
    ),
    tolerance: float = typer.Option(1e-9, "--tol", help="Verification tolerance (rel/abs)."),
) -> None:
    """Render the model to an .xlsx workbook (PRD §9.2). Verifies by default."""
    from .excel import export, verify

    try:
        model = _load_user_model(model_path)
        ovs = read_overrides(model_path.parent / "overrides.toml")
        model_ovs = [o for o in ovs if o.model is None or o.model == type(model).__name__]
        if model_ovs:
            apply_overrides(model, model_ovs)
        model.solve()
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    out_resolved = out if out.is_absolute() else model_path.parent / out
    written = export(model, out_resolved)
    typer.echo(f"✓ Exported to {written}")

    if skip_verify:
        return
    result = verify(model, written, tolerance=tolerance)
    if result.ok:
        typer.echo(f"✓ Verified: all {result.checked} cells match within {tolerance}")
        return
    typer.echo(
        f"✗ Verification failed: {len(result.mismatches)} of {result.checked} cells "
        f"differ; first {min(10, len(result.mismatches))} shown:",
        err=True,
    )
    for m in result.first_mismatches(10):
        typer.echo(
            f"   {m.label}[{m.period}] @ {m.sheet}!{m.cell}: "
            f"expected {m.expected!r}, got {m.actual!r}",
            err=True,
        )
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


@app.command(name="import")
def import_cmd(
    src: Path = typer.Argument(..., help="Path to .xlsx file to import."),
    out: Path = typer.Option(Path("."), "--out", help="Destination folder for the new model."),
    classname: str = typer.Option("Imported", "--classname", help="Generated class name."),
) -> None:
    """Convert ``.xlsx`` → ``sweet.py`` + ``sweet.md`` (PRD §9.1).

    Phase 2 is non-interactive: produces a Layer-1 skeleton with TODOs in
    ``sweet.md`` for ambiguities. Phase 3 wires this into the agent loop.
    """
    from .excel.import_ import import_xlsx, write_imported

    if not src.exists():
        typer.echo(f"✗ Source not found: {src}", err=True)
        raise typer.Exit(1)
    plan = import_xlsx(src, classname=classname)
    out.mkdir(parents=True, exist_ok=True)
    write_imported(plan, out)
    typer.echo(
        f"✓ Imported {src.name}: {len(plan.rows)} row(s), "
        f"{len(plan.globs)} glob(s) → {out}/sweet.py + sweet.md"
    )
    if plan.issues:
        typer.echo("Issues found (also recorded in sweet.md):")
        for issue in plan.issues:
            typer.echo(f"  - {issue}")


# ---------------------------------------------------------------------------
# describe
# ---------------------------------------------------------------------------


@app.command()
def describe(
    out: Path = typer.Option(
        Path("outputs/model.json"), "--out", help="Output .json path."
    ),
    model_path: Path = typer.Option(
        Path("sweet.py"), "--model", help="Path to the sweet.py file."
    ),
) -> None:
    """Export the model *definition* (DAG, source, docs, mermaid) to JSON.

    Unlike ``sweet run`` (which writes solved values to result.json), this
    captures each model's *shape*: globals + docs, per-row Python source +
    docstring + dependencies, axis specs, the variable-level DAG, and a
    mechanically generated Mermaid diagram. ``sweet.md`` is appended as
    ``documentation`` if present.

    With multiple models in the file, all are described in the ``models``
    list.
    """
    try:
        models = _load_all_models(model_path)
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    md_path = model_path.parent / "sweet.md"
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else None

    out_resolved = out if out.is_absolute() else model_path.parent / out
    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    out_resolved.write_text(json.dumps(describe_models(models, md_text), indent=2, default=str))
    typer.echo(f"✓ Wrote {out_resolved}")


# ---------------------------------------------------------------------------
# explain
# ---------------------------------------------------------------------------


@app.command()
def explain(
    target: str = typer.Argument(..., help="Row or scalar name to explain."),
    model_path: Path = typer.Option(
        Path("sweet.py"), "--model", help="Path to sweet.py."
    ),
) -> None:
    """Show the desugared (Layer-1) form of a row/scalar plus its dependencies."""
    from .sugar import class_scope, desugar_to_source

    model = _load_user_model(model_path)
    cls = type(model)
    rows = cls._rows  # pyright: ignore[reportPrivateUsage]
    scalars = cls._scalars  # pyright: ignore[reportPrivateUsage]
    if target in rows:
        kind = "row"
        deps = rows[target].explicit_deps
    elif target in scalars:
        kind = "scalar"
        deps = scalars[target].explicit_deps
    else:
        typer.echo(f"✗ Unknown row/scalar: {target}", err=True)
        raise typer.Exit(1)
    fn = (rows if kind == "row" else scalars)[target].fn
    scope = class_scope(cls)

    typer.echo(f"# {target} ({kind})")
    if deps:
        typer.echo(f"# depends on: {', '.join(sorted(deps))}")
    typer.echo("")
    try:
        src = desugar_to_source(fn, target, scope, kind=kind)
    except (OSError, ModelError):
        import inspect as _inspect

        src = _inspect.getsource(fn)
    typer.echo(src)


# ---------------------------------------------------------------------------
# overrides
# ---------------------------------------------------------------------------


def _overrides_path(model_path: Path) -> Path:
    return model_path.parent / "overrides.toml"


@overrides_app.command("add")
def overrides_add(
    target: str = typer.Argument(..., help="Row name (use --glob for a global)."),
    period: str = typer.Argument(None, help="Period (e.g. 2025). Omit for scalar/glob."),
    value: str = typer.Argument(..., help="Value to set (parsed as JSON if possible)."),
    reason: str = typer.Option("", "--reason", help="Why this override exists."),
    author: str = typer.Option("", "--author", help="Who recorded it."),
    is_glob: bool = typer.Option(False, "--glob", help="Override a global, not a row."),
    model_name: str = typer.Option(
        "", "--model-name", help="Restrict override to a specific Model class name."
    ),
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
) -> None:
    """Record an override in overrides.toml.

    Use ``--model-name ModelClassName`` to scope the override to a specific
    model when the file contains multiple Model classes.
    """
    path = _overrides_path(model_path)
    existing = read_overrides(path)
    parsed_value: Any
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value
    parsed_period: Any | None = None
    if period:
        try:
            parsed_period = int(period)
        except ValueError:
            parsed_period = period
    new = Override(
        target=target,
        value=parsed_value,
        period=parsed_period,
        reason=reason,
        author=author,
        kind="glob" if is_glob else "row",
        model=model_name or None,
    )
    # remove any prior matching entry (same target+period+kind+model)
    kept = [
        o
        for o in existing
        if not (
            o.target == new.target
            and o.period == new.period
            and o.kind == new.kind
            and o.model == new.model
        )
    ]
    kept.append(new)
    write_overrides(path, kept)
    typer.echo(f"✓ Recorded override: {target}{f'[{parsed_period}]' if parsed_period is not None else ''} = {parsed_value}")


@overrides_app.command("list")
def overrides_list(
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
) -> None:
    """List recorded overrides."""
    overrides = read_overrides(_overrides_path(model_path))
    if not overrides:
        typer.echo("(no overrides)")
        return
    for ov in overrides:
        head = f"{ov.target}[{ov.period}]" if ov.period is not None else ov.target
        kind = " (glob)" if ov.kind == "glob" else ""
        model_tag = f" [{ov.model}]" if ov.model else ""
        line = f"  {head}{kind}{model_tag} = {ov.value}"
        if ov.reason:
            line += f"  — {ov.reason}"
        if ov.author:
            line += f"  ({ov.author})"
        typer.echo(line)


@overrides_app.command("rm")
def overrides_rm(
    target: str = typer.Argument(...),
    period: str = typer.Argument(None),
    is_glob: bool = typer.Option(False, "--glob"),
    model_name: str = typer.Option("", "--model-name"),
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
) -> None:
    """Remove a recorded override."""
    path = _overrides_path(model_path)
    existing = read_overrides(path)
    parsed_period: Any | None = None
    if period:
        try:
            parsed_period = int(period)
        except ValueError:
            parsed_period = period
    kind = "glob" if is_glob else "row"
    scoped_model = model_name or None
    kept = [
        o for o in existing
        if not (
            o.target == target
            and o.period == parsed_period
            and o.kind == kind
            and o.model == scoped_model
        )
    ]
    if len(kept) == len(existing):
        typer.echo(f"✗ No matching override for {target}", err=True)
        raise typer.Exit(1)
    write_overrides(path, kept)
    typer.echo(f"✓ Removed override for {target}")


@overrides_app.command("clear")
def overrides_clear(
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Remove all overrides."""
    path = _overrides_path(model_path)
    if not path.exists():
        typer.echo("(no overrides)")
        return
    if not yes:
        typer.confirm(f"Remove all overrides from {path}?", abort=True)
    path.unlink()
    typer.echo(f"✓ Removed {path}")


# ---------------------------------------------------------------------------
# diff / snapshot (Phase 3)
# ---------------------------------------------------------------------------


def _solved_models(model_path: Path) -> list[Model]:
    models = _load_all_models(model_path)
    ovs = read_overrides(model_path.parent / "overrides.toml")
    for model in models:
        model_ovs = [o for o in ovs if o.model is None or o.model == type(model).__name__]
        if model_ovs:
            apply_overrides(model, model_ovs)
        model.solve()
    return models


@app.command()
def diff(
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
) -> None:
    """Compare the current solve to ``.model/snapshot.json`` (PRD §10.2)."""
    from .snapshot import (
        diff_cells,
        format_diff,
        read_snapshot,
        serialize_cells,
        serialize_cells_multi,
    )

    try:
        models = _solved_models(model_path)
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    snap = read_snapshot(model_path.parent)
    if snap is None:
        typer.echo(
            "(no snapshot yet — run `model snapshot accept` to record the current solve)"
        )
        return

    current = serialize_cells_multi(models) if len(models) > 1 else serialize_cells(models[0])
    report = diff_cells(current, snap)
    typer.echo(format_diff(report))
    if not report.empty:
        raise typer.Exit(1)


@snapshot_app.command("accept")
def snapshot_accept(
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
) -> None:
    """Pin the current solve as the new committed snapshot."""
    from .snapshot import serialize_cells, serialize_cells_multi, write_snapshot

    try:
        models = _solved_models(model_path)
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    cells = serialize_cells_multi(models) if len(models) > 1 else serialize_cells(models[0])
    path = write_snapshot(model_path.parent, cells)
    typer.echo(f"✓ Wrote snapshot to {path}")


@doc_app.command("sync")
def doc_sync(
    model_path: Path = typer.Option(Path("sweet.py"), "--model"),
) -> None:
    """Report drift between ``sweet.py`` and ``sweet.md`` (PRD §6).

    Phase 3 ships a report-only sync: prints the rows/scalars/globs
    declared in code that aren't mentioned in markdown, plus mentions
    that don't resolve to code. Use ``sweet agent`` for interactive
    reconciliation.
    """
    from .docsync import compare, format_drift

    md_path = model_path.parent / "sweet.md"
    if not md_path.exists():
        typer.echo(f"✗ No sweet.md found at {md_path}", err=True)
        raise typer.Exit(1)
    try:
        model = _load_user_model(model_path)
    except ModelError as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc
    drift = compare(model, md_path.read_text(encoding="utf-8"))
    typer.echo(format_drift(drift))
    if not drift.empty:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# agent (Phase 3)
# ---------------------------------------------------------------------------


@app.command()
def agent(
    workspace: Path = typer.Option(Path("."), "--workspace", help="Model workspace dir."),
    harness: str = typer.Option(
        "anthropic-api",
        "--harness",
        help="Harness backend: 'anthropic-api' (default) or 'claude-code'.",
    ),
    auto_confirm: bool = typer.Option(
        False, "--yes", "-y", help="Auto-approve all tool calls (use with care)."
    ),
    message: str = typer.Option(
        "", "--message", "-m", help="Send one opening message and exit after the reply."
    ),
) -> None:
    """Launch the interactive agent loop (PRD §8).

    Pluggable harnesses (Anthropic API, Claude Code, …) — see
    ``model/skills/harness-adapter/SKILL.md`` for adding your own.

    For ``--harness=anthropic-api`` you need ``ANTHROPIC_API_KEY``:

      1) Get a key: https://console.anthropic.com/settings/keys
      2) Export:    export ANTHROPIC_API_KEY=sk-ant-...
      3) Re-run:    model agent
    """
    from .agent.harness import get_harness
    from .agent.loop import LoopConfig, run_loop

    try:
        h = get_harness(harness)
    except (KeyError, RuntimeError) as exc:
        typer.echo(f"✗ {exc}", err=True)
        raise typer.Exit(1) from exc

    config = LoopConfig(
        workspace=workspace.resolve(),
        harness=h,
        auto_confirm_tools=auto_confirm,
        max_turns=1 if message else 50,
    )
    run_loop(config, opening_user_message=message or None)


if __name__ == "__main__":
    app()
