"""Structured JSON serialization for model outputs and definitions.

Two shapes live here:

  - ``to_json(model)`` mirrors the *solved* model: axes, glob values,
    one "table" per ``@row`` (with columns + per-period results), and
    scalars. Used by ``sweet run`` → ``outputs/result.json``.

  - ``describe_model(model, md_text=...)`` mirrors the *defined* model:
    DAG between variables, per-row Python source + docstring + deps,
    column specs, optional sweet.md documentation appended, and a
    mechanically generated Mermaid diagram. Used by ``sweet describe``
    → ``outputs/model.json``.

Snapshots intentionally keep the flat shape (``snapshot.serialize_cells``)
because cell-level diffing wants stable, simple keys.
"""

from __future__ import annotations

import inspect
import textwrap
from typing import Any

from .core import Dim, Model, Periods
from .solver import _node_dependencies


def _type_name(v: Any) -> str:
    return type(v).__name__


def _axis_spec(axis: Dim | Periods) -> dict[str, Any]:
    if isinstance(axis, Periods):
        return {"kind": "periods", "values": list(axis.values)}
    return {"kind": "dim", "values": list(axis.values)}


def _glob_entries(model: Model) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, descr in type(model)._globs.items():
        value = getattr(model, name)
        out[name] = {
            "value": value,
            "default": descr.default,
            "type": _type_name(value),
            "doc": descr.doc,
        }
    return out


def _format_period_key(idx: tuple[Any, ...]) -> str:
    if len(idx) == 1:
        return str(idx[0])
    return ",".join(str(x) for x in idx)


def _known(model: Model) -> set[str]:
    cls = type(model)
    return (
        set(cls._rows)
        | set(cls._scalars)
        | set(cls._globs)
        | set(cls._depends)  # pyright: ignore[reportPrivateUsage]
    )


def _row_entries(model: Model) -> list[dict[str, Any]]:
    cls = type(model)
    cells = model._cells  # pyright: ignore[reportPrivateUsage]
    known = _known(model)
    tables: list[dict[str, Any]] = []
    for name, r in cls._rows.items():
        if r.over is not None:
            columns = [_axis_spec(a) for a in r.over]
        else:
            columns = [_axis_spec(model.time)]
        results: dict[str, Any] = {}
        for key, value in cells.items():
            row_name, *idx = key
            if row_name != name:
                continue
            results[_format_period_key(tuple(idx))] = value
        tables.append({
            "name": name,
            "kind": "row",
            "doc": inspect.getdoc(r.fn),
            "depends_on": _node_deps(name, r.fn, known, r.explicit_deps),
            "columns": columns,
            "results": results,
        })
    return tables


def _scalar_entries(model: Model) -> list[dict[str, Any]]:
    cls = type(model)
    cells = model._cells  # pyright: ignore[reportPrivateUsage]
    known = _known(model)
    scalars: list[dict[str, Any]] = []
    for name, s in cls._scalars.items():
        value = cells.get((name, None))
        scalars.append({
            "name": name,
            "kind": "scalar",
            "doc": inspect.getdoc(s.fn),
            "depends_on": _node_deps(name, s.fn, known, s.explicit_deps),
            "type": _type_name(value),
            "value": value,
        })
    return scalars


def _axes(model: Model) -> dict[str, dict[str, Any]]:
    cls = type(model)
    out: dict[str, dict[str, Any]] = {}
    for name, p in cls._periods_attrs.items():
        out[name] = _axis_spec(p)
    for name, d in cls._dims.items():
        out[name] = _axis_spec(d)
    return out


def _source_of(fn: Any) -> str | None:
    try:
        return textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None


def _node_deps(name: str, fn: Any, known: set[str], explicit: set[str] | None) -> list[str]:
    if explicit is not None:
        return sorted(explicit)
    return sorted(_node_dependencies(name, fn, known))


def _build_dag(model: Model) -> dict[str, Any]:
    """Variable-level DAG: globs/depends feed rows/scalars; rows/scalars feed each other.

    Globals and cross-model depends() appear as source nodes so the diagram
    shows the full data-flow into derived values.
    """
    cls = type(model)
    rows = cls._rows
    scalars = cls._scalars
    globs = cls._globs
    dep_models = cls._depends  # pyright: ignore[reportPrivateUsage]
    known = set(rows) | set(scalars) | set(globs) | set(dep_models)
    nodes = [
        {"name": n, "kind": "glob"} for n in sorted(globs)
    ] + [
        {"name": n, "kind": "depends"} for n in sorted(dep_models)
    ] + [
        {"name": n, "kind": "row"} for n in sorted(rows)
    ] + [
        {"name": n, "kind": "scalar"} for n in sorted(scalars)
    ]
    edges: list[dict[str, str]] = []
    for name, r in rows.items():
        for dep in _node_deps(name, r.fn, known, r.explicit_deps):
            edges.append({"from": dep, "to": name})
    for name, s in scalars.items():
        for dep in _node_deps(name, s.fn, known, s.explicit_deps):
            edges.append({"from": dep, "to": name})
    return {"nodes": nodes, "edges": edges}


def _to_mermaid(dag: dict[str, Any]) -> str:
    """Render a DAG dict as a Mermaid ``graph TD``.

    Shape per kind: globs as stadium ``([…])``, scalars as circle ``((…))``,
    rows as plain rectangles. No edge labels — the JSON has the rest.
    """
    lines = ["graph TD"]
    for node in dag["nodes"]:
        n, kind = node["name"], node["kind"]
        if kind == "glob":
            lines.append(f"    {n}([{n}])")
        elif kind == "scalar":
            lines.append(f"    {n}(({n}))")
        elif kind == "depends":
            lines.append(f"    {n}[/{n}/]")
        else:
            lines.append(f"    {n}[{n}]")
    for e in dag["edges"]:
        lines.append(f"    {e['from']} --> {e['to']}")
    return "\n".join(lines)


def _glob_definitions(model: Model) -> dict[str, dict[str, Any]]:
    """Static glob spec — default + doc + type, no current value."""
    out: dict[str, dict[str, Any]] = {}
    for name, descr in type(model)._globs.items():
        out[name] = {
            "default": descr.default,
            "type": _type_name(descr.default),
            "doc": descr.doc,
        }
    return out


def _row_definitions(model: Model) -> list[dict[str, Any]]:
    cls = type(model)
    rows = cls._rows
    scalars = cls._scalars
    globs = cls._globs
    known = set(rows) | set(scalars) | set(globs) | set(cls._depends)  # pyright: ignore[reportPrivateUsage]
    out: list[dict[str, Any]] = []
    for name, r in rows.items():
        if r.over is not None:
            columns = [_axis_spec(a) for a in r.over]
        else:
            columns = [_axis_spec(model.time)] if cls._periods_attrs else []
        out.append({
            "name": name,
            "kind": "row",
            "doc": inspect.getdoc(r.fn),
            "depends_on": _node_deps(name, r.fn, known, r.explicit_deps),
            "columns": columns,
            "source": _source_of(r.fn),
        })
    return out


def _scalar_definitions(model: Model) -> list[dict[str, Any]]:
    cls = type(model)
    rows = cls._rows
    scalars = cls._scalars
    globs = cls._globs
    known = set(rows) | set(scalars) | set(globs) | set(cls._depends)  # pyright: ignore[reportPrivateUsage]
    out: list[dict[str, Any]] = []
    for name, s in scalars.items():
        out.append({
            "name": name,
            "kind": "scalar",
            "doc": inspect.getdoc(s.fn),
            "depends_on": _node_deps(name, s.fn, known, s.explicit_deps),
            "source": _source_of(s.fn),
        })
    return out


def _describe_single(model: Model) -> dict[str, Any]:
    """Serialize one Model's definition — DAG, source, docs, columns."""
    cls = type(model)
    dag = _build_dag(model)
    return {
        "name": cls.__name__,
        "doc": inspect.getdoc(cls) if cls.__doc__ else None,
        "axes": _axes(model),
        "globals": _glob_definitions(model),
        "rows": _row_definitions(model),
        "scalars": _scalar_definitions(model),
        "dag": dag,
        "mermaid": _to_mermaid(dag),
    }


def describe_models(models: list[Model], md_text: str | None = None) -> dict[str, Any]:
    """Serialize the *definition* of one or more Models.

    Top-level keys:
      - ``models``: one entry per Model class, each with ``name``, ``doc``,
        ``axes``, ``globals``, ``rows``, ``scalars``, ``dag``, ``mermaid``.
      - ``documentation``: the contents of ``sweet.md`` if provided.

    The DAG per model includes globals as source nodes so the diagram shows
    the full data-flow, not just inter-row plumbing.
    """
    return {"models": [_describe_single(m) for m in models], "documentation": md_text}


def describe_model(model: Model, md_text: str | None = None) -> dict[str, Any]:
    """Serialize a single Model's definition. Delegates to describe_models()."""
    return describe_models([model], md_text)


def to_json_multi(models: list[Model]) -> dict[str, Any]:
    """Serialize one or more solved Models into a combined result dict.

    Top-level key ``models`` is a list; each entry has the same shape as
    ``to_json()`` (``model``, ``inputs``, ``tables``, ``scalars``).
    """
    return {"models": [to_json(m) for m in models]}


def to_json(model: Model) -> dict[str, Any]:
    """Serialize a solved ``Model`` into a structured, model-shaped dict.

    Top-level keys:
      - ``model``:  ``{name, doc, axes}``
      - ``inputs``: ``{glob_name: {value, default, type, doc}}``
      - ``tables``: one entry per ``@row`` with ``columns``, ``results``,
        ``depends_on``, ``doc``.
      - ``scalars``: one entry per ``@scalar`` with ``value``, ``type``,
        ``depends_on``, ``doc``.
    """
    cls = type(model)
    return {
        "model": {
            "name": cls.__name__,
            "doc": inspect.getdoc(cls) if cls.__doc__ else None,
            "axes": _axes(model),
        },
        "inputs": _glob_entries(model),
        "tables": _row_entries(model),
        "scalars": _scalar_entries(model),
    }
