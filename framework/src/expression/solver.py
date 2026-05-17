"""Eager DAG solver (Phase 0).

Steps:

1. Statically analyze each ``@row`` method's source via :mod:`ast` to find
   references to *other* rows of the form ``self.<other_row>(...)``. Self-
   references (``self.budget(t-1)``) are *not* dependencies — they are temporal
   lags within the same row.
2. Build a :class:`networkx.DiGraph` with rows as nodes and inter-row deps as
   edges. Detect cycles and report them.
3. Topologically sort. For each row, iterate periods in order and call the
   row's bound method, which caches into ``model._cells``.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import itertools
import textwrap
import types
from typing import TYPE_CHECKING

import networkx as nx

from .core import CircularReferenceError, ModelError

if TYPE_CHECKING:
    from .core import Model


class _LocalNameCollector(ast.NodeVisitor):
    """Collect names bound inside a function so globals can be distinguished."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_arg(self, node: ast.arg) -> None:
        self.names.add(node.arg)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)
        self.generic_visit(node)


def _is_trackable_global(value: object) -> bool:
    """Return whether a module global is data-like enough to report as a dep."""
    return not (
        isinstance(value, types.ModuleType)
        or inspect.isclass(value)
        or inspect.isroutine(value)
        or inspect.ismethoddescriptor(value)
    )


def _module_global_dependencies(fn: object, tree: ast.AST, known: set[str]) -> set[str]:
    fn_globals = getattr(fn, "__globals__", None)
    if not isinstance(fn_globals, dict):
        return set()

    collector = _LocalNameCollector()
    collector.visit(tree)
    builtin_names = set(dir(builtins))
    deps: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        name = node.id
        if (
            name in known
            or name in collector.names
            or name in builtin_names
            or name.startswith("__")
            or name not in fn_globals
        ):
            continue
        if _is_trackable_global(fn_globals[name]):
            deps.add(name)
    return deps


def _node_dependencies(
    self_name: str,
    fn: object,
    known: set[str],
    *,
    include_module_globals: bool = False,
) -> set[str]:
    """Return other nodes referenced by a row/scalar function.

    ``known`` covers model attributes such as rows, scalars, globs, and depends().
    When requested, module-level data globals read by the function are reported
    too so ``describe`` can show dependencies on constants outside the class.
    """
    try:
        source = textwrap.dedent(inspect.getsource(fn))  # type: ignore[arg-type]
    except (OSError, TypeError):
        return set()
    tree = ast.parse(source)
    deps: set[str] = set()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr in known
            and node.attr != self_name
        ):
            deps.add(node.attr)
    if include_module_globals:
        deps.update(_module_global_dependencies(fn, tree, known))
    return deps


def build_dag(model: Model) -> nx.DiGraph:
    """Return a DiGraph with an edge ``dep -> node`` for each inter-node dep.

    Nodes are rows (period-axis) and scalars (single-value) on the model.
    """
    g: nx.DiGraph = nx.DiGraph()
    rows = model._rows  # pyright: ignore[reportPrivateUsage]
    scalars = model._scalars  # pyright: ignore[reportPrivateUsage]
    dep_models = model._depends  # pyright: ignore[reportPrivateUsage]
    known = set(rows) | set(scalars) | set(dep_models)
    for name in set(rows) | set(scalars):
        g.add_node(name)
    for name, row_obj in rows.items():
        deps = (
            row_obj.explicit_deps
            if row_obj.explicit_deps is not None
            else _node_dependencies(name, row_obj.fn, known)
        )
        for dep in deps:
            g.add_edge(dep, name)
    for name, scalar_obj in scalars.items():
        deps = (
            scalar_obj.explicit_deps
            if scalar_obj.explicit_deps is not None
            else _node_dependencies(name, scalar_obj.fn, known)
        )
        for dep in deps:
            g.add_edge(dep, name)
    return g


def eager_solve(model: Model) -> None:
    """Topologically sort nodes, then evaluate rows across periods + scalars."""
    g = build_dag(model)
    try:
        order = list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as exc:
        cycles = list(nx.simple_cycles(g))
        cycle_str = " ; ".join(" -> ".join([*c, c[0]]) for c in cycles)
        raise ModelError(f"Circular dependency between rows: {cycle_str}") from exc

    rows = model._rows  # pyright: ignore[reportPrivateUsage]
    scalars = model._scalars  # pyright: ignore[reportPrivateUsage]

    has_periods = bool(model._periods_attrs)  # pyright: ignore[reportPrivateUsage]
    time = model.time if has_periods else None

    for name in order:
        if name in rows:
            row_obj = rows[name]
            bound = getattr(model, name)
            if row_obj.over is not None:
                axes_values = [list(axis) for axis in row_obj.over]
                for combo in itertools.product(*axes_values):
                    try:
                        bound(*combo)
                    except CircularReferenceError:
                        raise
                    except Exception as exc:
                        raise ModelError(
                            f"Error evaluating {name}{list(combo)}: "
                            f"{type(exc).__name__}: {exc}"
                        ) from exc
            else:
                if time is None:
                    raise ModelError(f"Row {name!r} requires a periods(...) axis")
                for t in time:
                    try:
                        bound(t)
                    except CircularReferenceError:
                        raise
                    except Exception as exc:
                        raise ModelError(
                            f"Error evaluating {name}[{t}]: {type(exc).__name__}: {exc}"
                        ) from exc
        elif name in scalars:
            try:
                getattr(model, name)  # triggers Scalar.__get__ → caches
            except CircularReferenceError:
                raise
            except Exception as exc:
                raise ModelError(
                    f"Error evaluating {name}: {type(exc).__name__}: {exc}"
                ) from exc
