"""Layer 2 (AST sugar) for ``@row`` / ``@scalar`` (PRD §3.1, §3.3, §3.5).

A Layer-2 row body looks like::

    @row
    def budget():
        budget[first] = seed
        budget[n]     = budget[n-1] * (1 + growth_rate)

We rewrite this at class definition time into the Layer-1 equivalent::

    @row
    def budget(self, t):
        if t == self.time.first:
            return self.seed
        return self.budget(t - 1) * (1 + self.growth_rate)

Recognition rule: a function with no positional arguments is Layer 2. With at
least ``self``, it is Layer 1 and passes through unchanged. Sugar is on by
default; opt-out per class via ``class Foo(Model, sugar=False):``.

What's supported (Phase 1):
- Assignments ``name[<key>] = <expr>`` for keys: ``first``, ``last``, ``n``,
  ``t``, integer literal, or any expression involving ``n``/``t`` (treated as
  the default-rule guard with the LHS bound to the current period).
- Reads ``name[<key>]`` for the same set, plus ``n-k`` lag form.
- ``name[:]`` → full series; ``name[a:b]`` → inclusive-end window list.
- Bare global / scalar / depends names → ``self.<name>``.
- Implicit ``self``: scope walker prefixes ``self.`` for any free name that
  resolves to a model attribute (rows, scalars, globs, depends, periods).

Inspectability: the rewriter stores ``Row.desugared_source`` and
``Row.desugared_tree`` so ``sweet explain`` can show the Layer-1 form.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .core import Model, ModelError, Periods, Row, Scalar


@dataclass
class _Scope:
    rows: set[str]
    scalars: set[str]
    globs: set[str]
    depends: set[str]
    periods_attrs: set[str]  # attribute names holding Periods instances
    period_alias: tuple[str, ...] = ("n", "t")  # bare names that mean "current period"

    @property
    def model_attrs(self) -> set[str]:
        return self.rows | self.scalars | self.globs | self.depends | self.periods_attrs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_layer2(fn: Callable[..., Any]) -> bool:
    """A function is Layer 2 if it has no positional args (no ``self``)."""
    sig = inspect.signature(fn)
    return len(sig.parameters) == 0


def _make_self_attr(name: str, ctx: ast.expr_context | None = None) -> ast.Attribute:
    return ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr=name,
        ctx=ctx or ast.Load(),
    )


def _self_call(method: str, *args: ast.expr) -> ast.Call:
    return ast.Call(func=_make_self_attr(method), args=list(args), keywords=[])


def _is_period_alias(node: ast.expr, scope: _Scope) -> bool:
    return isinstance(node, ast.Name) and node.id in scope.period_alias


# ---------------------------------------------------------------------------
# Read-side transform: turn Layer-2 reads into Layer-1 reads.
# ---------------------------------------------------------------------------


class _ReadTransformer(ast.NodeTransformer):
    """Rewrite reads in expression positions (no LHS subscripts)."""

    def __init__(self, scope: _Scope) -> None:
        self.scope = scope

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        # Look at the *original* value before transforming children, so we can
        # see ``Name('budget')`` and rewrite the whole subscript instead of
        # letting visit_Name turn it into ``self.budget`` first.
        if not isinstance(node.value, ast.Name) or (
            node.value.id not in self.scope.rows and node.value.id not in self.scope.scalars
        ):
            # Not a row/scalar subscript — recurse into children normally.
            self.generic_visit(node)
            return node
        target = node.value.id
        sl = node.slice
        # Recurse into the slice expression so nested rows/globs get rewritten.
        if isinstance(sl, ast.Slice):
            sl = ast.Slice(
                lower=self.visit(sl.lower) if sl.lower is not None else None,
                upper=self.visit(sl.upper) if sl.upper is not None else None,
                step=self.visit(sl.step) if sl.step is not None else None,
            )
        else:
            sl = self.visit(sl)
        node = ast.Subscript(value=node.value, slice=sl, ctx=node.ctx)
        # name[:] — full series
        if isinstance(sl, ast.Slice) and sl.lower is None and sl.upper is None and sl.step is None:
            return ast.Call(
                func=_make_self_attr("series"),
                args=[ast.Constant(value=target)],
                keywords=[],
            )
        # name[a:b] — inclusive window from period a..b
        if isinstance(sl, ast.Slice):
            lo = sl.lower
            hi = sl.upper
            if lo is None or hi is None:
                raise ModelError(
                    f"Layer-2: open-ended slices like name[:n] are not supported in Phase 1 "
                    f"(row {target!r})"
                )
            # [self.<target>(p) for p in range(lo, hi + 1)]
            comprehension = ast.ListComp(
                elt=_self_call(target, ast.Name(id="_p", ctx=ast.Load())),
                generators=[
                    ast.comprehension(
                        target=ast.Name(id="_p", ctx=ast.Store()),
                        iter=ast.Call(
                            func=ast.Name(id="range", ctx=ast.Load()),
                            args=[
                                lo,
                                ast.BinOp(left=hi, op=ast.Add(), right=ast.Constant(value=1)),
                            ],
                            keywords=[],
                        ),
                        ifs=[],
                        is_async=0,
                    )
                ],
            )
            return comprehension
        # name[<period_expr>] — single cell read
        period = self._period_expr(sl)
        return _self_call(target, period)

    def _period_expr(self, sl: ast.expr) -> ast.expr:
        # first/last
        if isinstance(sl, ast.Name) and sl.id == "first":
            return ast.Attribute(value=_make_self_attr("time"), attr="first", ctx=ast.Load())
        if isinstance(sl, ast.Name) and sl.id == "last":
            return ast.Attribute(value=_make_self_attr("time"), attr="last", ctx=ast.Load())
        # bare n/t → t (function arg)
        if _is_period_alias(sl, self.scope):
            return ast.Name(id="t", ctx=ast.Load())
        # general expression — replace nested n/t with t
        return _PeriodAliasReplacer(self.scope).visit(sl)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        # Bare global / scalar / depends / periods → self.<name>
        if isinstance(node.ctx, ast.Load) and node.id in self.scope.model_attrs:
            return _make_self_attr(node.id)
        return node


class _PeriodAliasReplacer(ast.NodeTransformer):
    """Replace ``n`` / ``t`` (period aliases) with the function's ``t`` arg."""

    def __init__(self, scope: _Scope) -> None:
        self.scope = scope

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if isinstance(node.ctx, ast.Load) and node.id in self.scope.period_alias:
            return ast.Name(id="t", ctx=ast.Load())
        if isinstance(node.ctx, ast.Load) and node.id == "first":
            return ast.Attribute(value=_make_self_attr("time"), attr="first", ctx=ast.Load())
        if isinstance(node.ctx, ast.Load) and node.id == "last":
            return ast.Attribute(value=_make_self_attr("time"), attr="last", ctx=ast.Load())
        return node


# ---------------------------------------------------------------------------
# Row body transform: assignments into branches.
# ---------------------------------------------------------------------------


def _classify_lhs(target: ast.expr, row_name: str, scope: _Scope) -> ast.expr | None:
    """For a Layer-2 LHS ``row_name[<key>]``, return the guard expression for ``t``,
    or ``None`` if the key is the default (``n`` / ``t``).

    A guard expression is the value to compare ``t`` against; e.g.,
    ``self.time.first``, an integer literal, etc.
    """
    if not isinstance(target, ast.Subscript):
        raise ModelError(
            f"Layer-2 row {row_name!r}: assignment target must be subscript, got "
            f"{ast.dump(target)}"
        )
    if not isinstance(target.value, ast.Name) or target.value.id != row_name:
        raise ModelError(
            f"Layer-2 row {row_name!r}: assignment must target self ({row_name}[...]), "
            f"got {ast.dump(target.value)}"
        )
    sl = target.slice
    if isinstance(sl, ast.Name) and sl.id == "first":
        return ast.Attribute(value=_make_self_attr("time"), attr="first", ctx=ast.Load())
    if isinstance(sl, ast.Name) and sl.id == "last":
        return ast.Attribute(value=_make_self_attr("time"), attr="last", ctx=ast.Load())
    if _is_period_alias(sl, scope):
        return None  # default rule
    return _PeriodAliasReplacer(scope).visit(sl)


def _layer2_deps_from_tree(tree: ast.AST, scope: _Scope, exclude: str) -> set[str]:
    """Walk a *Layer-2* AST and collect referenced row/scalar names.

    Recognizes ``name[...]`` subscripts and bare ``name`` references where
    ``name`` is a known row or scalar.
    """
    deps: set[str] = set()
    known = scope.rows | scope.scalars
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in known
            and node.value.id != exclude
        ):
            deps.add(node.value.id)
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in known
            and node.id != exclude
        ):
            deps.add(node.id)
    return deps


def _desugar_row(
    fn: Callable[..., Any], row_name: str, scope: _Scope
) -> tuple[Callable[..., Any], set[str]]:
    """Rewrite a Layer-2 row function into Layer-1 form (``self, t``)."""
    src = textwrap.dedent(inspect.getsource(fn))
    module = ast.parse(src)
    funcdef = module.body[0]
    if not isinstance(funcdef, ast.FunctionDef):
        raise ModelError(f"Layer-2 row {row_name!r}: expected a function definition")
    deps = _layer2_deps_from_tree(module, scope, exclude=row_name)

    branches: list[tuple[ast.expr | None, ast.expr]] = []  # (guard|None, return-expr)
    for stmt in funcdef.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring / pass-through
        if not isinstance(stmt, ast.Assign):
            raise ModelError(
                f"Layer-2 row {row_name!r}: body must be assignments only, "
                f"got {type(stmt).__name__}"
            )
        if len(stmt.targets) != 1:
            raise ModelError(f"Layer-2 row {row_name!r}: tuple assignment not supported")
        guard = _classify_lhs(stmt.targets[0], row_name, scope)
        rhs = _ReadTransformer(scope).visit(stmt.value)
        branches.append((guard, rhs))

    body: list[ast.stmt] = []
    default_branches = [b for b in branches if b[0] is None]
    if len(default_branches) > 1:
        raise ModelError(
            f"Layer-2 row {row_name!r}: multiple default rules ({len(default_branches)})"
        )

    for guard, expr in branches:
        if guard is None:
            continue
        body.append(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="t", ctx=ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[guard],
                ),
                body=[ast.Return(value=expr)],
                orelse=[],
            )
        )
    if default_branches:
        body.append(ast.Return(value=default_branches[0][1]))
    else:
        body.append(
            ast.Raise(
                exc=ast.Call(
                    func=ast.Name(id="ModelError", ctx=ast.Load()),
                    args=[
                        ast.JoinedStr(
                            values=[
                                ast.Constant(value=f"No rule for {row_name}["),
                                ast.FormattedValue(
                                    value=ast.Name(id="t", ctx=ast.Load()),
                                    conversion=-1,
                                    format_spec=None,
                                ),
                                ast.Constant(value="]"),
                            ]
                        )
                    ],
                    keywords=[],
                ),
                cause=None,
            )
        )

    return _build_function(funcdef.name, ["self", "t"], body, fn), deps


def _desugar_scalar(
    fn: Callable[..., Any], scope: _Scope
) -> tuple[Callable[..., Any], set[str]]:
    src = textwrap.dedent(inspect.getsource(fn))
    module = ast.parse(src)
    funcdef = module.body[0]
    if not isinstance(funcdef, ast.FunctionDef):
        raise ModelError(f"Layer-2 scalar {fn.__name__!r}: expected a function definition")
    deps = _layer2_deps_from_tree(module, scope, exclude=funcdef.name)
    body: list[ast.stmt] = []
    for stmt in funcdef.body:
        body.append(_ReadTransformer(scope).visit(stmt))
    return _build_function(funcdef.name, ["self"], body, fn), deps


def _build_function(
    name: str,
    arg_names: list[str],
    body: list[ast.stmt],
    original: Callable[..., Any],
) -> Callable[..., Any]:
    new_funcdef = ast.FunctionDef(
        name=name,
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=a) for a in arg_names],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
            vararg=None,
            kwarg=None,
        ),
        body=body or [ast.Pass()],
        decorator_list=[],
        returns=None,
    )
    module = ast.Module(body=[new_funcdef], type_ignores=[])
    ast.fix_missing_locations(module)
    filename = getattr(original, "__code__", None)
    filename = filename.co_filename if filename else "<sugar>"
    code = compile(module, filename, "exec")
    ns: dict[str, Any] = {"ModelError": ModelError}
    exec(code, original.__globals__, ns)
    new_fn = ns[name]
    new_fn.__qualname__ = original.__qualname__
    new_fn.__module__ = original.__module__
    return new_fn


# ---------------------------------------------------------------------------
# Public entrypoint: called from Model.__init_subclass__.
# ---------------------------------------------------------------------------


def desugar_class(cls: type[Model]) -> None:
    """Rewrite all Layer-2 ``@row``/``@scalar`` methods on ``cls`` in place.

    Looks at the class dicts populated by ``Model.__init_subclass__`` and
    transforms only those methods whose original function had no positional
    args (Layer 2). Layer-1 methods are left alone.
    """
    rows: dict[str, Row] = cls._rows  # pyright: ignore[reportPrivateUsage]
    scalars: dict[str, Scalar] = cls._scalars  # pyright: ignore[reportPrivateUsage]
    glob_names: set[str] = set(cls._globs)  # pyright: ignore[reportPrivateUsage]
    depends_names: set[str] = set(cls._depends)  # pyright: ignore[reportPrivateUsage]

    periods_names: set[str] = set()
    for name, attr in vars(cls).items():
        if isinstance(attr, Periods):
            periods_names.add(name)
    # Walk MRO for inherited periods.
    for base in cls.__mro__[1:]:
        if base is Model or base is object:
            continue
        for name, attr in vars(base).items():
            if isinstance(attr, Periods):
                periods_names.add(name)

    scope = _Scope(
        rows=set(rows),
        scalars=set(scalars),
        globs=glob_names,
        depends=depends_names,
        periods_attrs=periods_names,
    )

    for row_name, row_obj in rows.items():
        if _is_layer2(row_obj.fn):
            new_fn, deps = _desugar_row(row_obj.fn, row_name, scope)
            row_obj.fn = new_fn
            row_obj.explicit_deps = deps

    for _scalar_name, scalar_obj in scalars.items():
        if _is_layer2(scalar_obj.fn):
            new_fn, deps = _desugar_scalar(scalar_obj.fn, scope)
            scalar_obj.fn = new_fn
            scalar_obj.explicit_deps = deps


def desugar_to_source(
    fn: Callable[..., Any], name: str, scope: _Scope, kind: str = "row"
) -> str:
    """Return the Layer-1 *source* form of a Layer-2 function (for explain)."""
    src = textwrap.dedent(inspect.getsource(fn))
    module = ast.parse(src)
    funcdef = module.body[0]
    if not isinstance(funcdef, ast.FunctionDef):
        return src
    if kind == "row":
        new_body: list[ast.stmt] = []
        branches: list[tuple[ast.expr | None, ast.expr]] = []
        for stmt in funcdef.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            if not isinstance(stmt, ast.Assign):
                continue
            guard = _classify_lhs(stmt.targets[0], name, scope)
            rhs = _ReadTransformer(scope).visit(stmt.value)
            branches.append((guard, rhs))
        for g, e in branches:
            if g is None:
                continue
            new_body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id="t", ctx=ast.Load()),
                        ops=[ast.Eq()],
                        comparators=[g],
                    ),
                    body=[ast.Return(value=e)],
                    orelse=[],
                )
            )
        defaults = [b for b in branches if b[0] is None]
        if defaults:
            new_body.append(ast.Return(value=defaults[0][1]))
        new_funcdef = ast.FunctionDef(
            name=funcdef.name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="self"), ast.arg(arg="t")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
                vararg=None,
                kwarg=None,
            ),
            body=new_body or [ast.Pass()],
            decorator_list=[ast.Name(id="row", ctx=ast.Load())],
            returns=None,
        )
    else:  # scalar
        body: list[ast.stmt] = []
        for stmt in funcdef.body:
            body.append(_ReadTransformer(scope).visit(stmt))
        new_funcdef = ast.FunctionDef(
            name=funcdef.name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="self")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
                vararg=None,
                kwarg=None,
            ),
            body=body or [ast.Pass()],
            decorator_list=[ast.Name(id="scalar", ctx=ast.Load())],
            returns=None,
        )
    ast.fix_missing_locations(new_funcdef)
    return ast.unparse(new_funcdef)


def class_scope(cls: type[Model]) -> _Scope:
    """Build the same scope that ``desugar_class`` uses, for outside callers."""
    periods_names: set[str] = set()
    for base in (*cls.__mro__,):
        if base is object:
            continue
        for name, attr in vars(base).items():
            if isinstance(attr, Periods):
                periods_names.add(name)
    return _Scope(
        rows=set(cls._rows),
        scalars=set(cls._scalars),
        globs=set(cls._globs),
        depends=set(cls._depends),
        periods_attrs=periods_names,
    )
