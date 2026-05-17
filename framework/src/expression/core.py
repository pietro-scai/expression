"""Core DSL primitives for Phase 0 (Layer 1 only).

Layer 1 means: pure-Python decorators, no AST sugar. A row is a method that takes
``self`` and the period label and returns the value for that period:

    class Budget(Model):
        time = periods(2024, 2028)
        seed = glob(100)
        growth_rate = glob(0.05)

        @row
        def budget(self, t):
            if t == self.time.first:
                return self.seed
            return self.budget(t - 1) * (1 + self.growth_rate)

The :func:`row` decorator returns a descriptor that, on bound access, gives a
callable which caches per ``(row, period)`` so that recursive references like
``self.budget(t - 1)`` see the already-computed value.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from itertools import product as _product
from typing import Any, ClassVar


class ModelError(Exception):
    """Base class for model errors."""


class CircularReferenceError(ModelError):
    """Raised when a cell depends on itself within the same evaluation."""


class Periods:
    """A discrete, ordered axis of period labels (currently integer years)."""

    def __init__(self, start: int, end: int) -> None:
        if end < start:
            raise ValueError(f"periods({start}, {end}): end must be >= start")
        self.start = start
        self.end = end
        self.values: list[int] = list(range(start, end + 1))

    @property
    def first(self) -> int:
        return self.values[0]

    @property
    def last(self) -> int:
        return self.values[-1]

    def __iter__(self) -> Iterator[int]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __contains__(self, t: object) -> bool:
        return t in self.values

    def __repr__(self) -> str:
        return f"periods({self.start}, {self.end})"


def periods(start: int, end: int) -> Periods:
    """Define an inclusive period range."""
    return Periods(start, end)


class Dim:
    """A discrete, ordered axis of categorical labels (PRD §3.4)."""

    def __init__(self, values: Sequence[Any]) -> None:
        if not values:
            raise ValueError("dim() requires at least one value")
        self.values: list[Any] = list(values)
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __iter__(self) -> Iterator[Any]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __contains__(self, v: object) -> bool:
        return v in self.values

    def __repr__(self) -> str:
        return f"dim({self.values!r})"


def dim(values: Iterable[Any]) -> Dim:
    """Declare a categorical axis (a list of labels)."""
    return Dim(list(values))


class Matrix:
    """A parameter table indexed by one or more axes (PRD §3.4).

    Construction:
      ``matrix(products, regions, default=10.0)`` → 2-D table.

    Read:
      ``self.base_price[p, r]`` returns the stored value (or default).

    Write:
      ``self.base_price[p, r] = 12.5`` overrides for that index.
    """

    def __init__(
        self,
        *axes: Dim | Periods,
        default: Any = None,
    ) -> None:
        if not axes:
            raise ValueError("matrix(...) requires at least one axis")
        self.axes: tuple[Dim | Periods, ...] = axes
        self.default: Any = default
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        cache: dict[str, _MatrixView] = obj.__dict__.setdefault("_matrix_views", {})
        if self._name not in cache:
            cache[self._name] = _MatrixView(self, obj)
        return cache[self._name]


class _MatrixView:
    """Per-instance accessor for a Matrix, allowing read/write semantics."""

    __slots__ = ("_matrix", "_overrides")

    def __init__(self, matrix: Matrix, owner: Any) -> None:
        self._matrix = matrix
        self._overrides: dict[tuple[Any, ...] | Any, Any] = owner.__dict__.setdefault(
            f"_matrix_data_{matrix._name}", {}
        )

    def _normalize_key(self, key: Any) -> tuple[Any, ...]:
        if isinstance(key, tuple):
            return key
        return (key,)

    def __getitem__(self, key: Any) -> Any:
        nkey = self._normalize_key(key)
        if len(nkey) != len(self._matrix.axes):
            raise ModelError(
                f"matrix {self._matrix._name!r}: expected "
                f"{len(self._matrix.axes)} indices, got {len(nkey)}"
            )
        if nkey in self._overrides:
            return self._overrides[nkey]
        default = self._matrix.default
        # PRD example 12.4 uses {'A': 10, 'B': 25} for a 1-D default.
        if isinstance(default, dict) and len(nkey) == 1 and nkey[0] in default:
            return default[nkey[0]]
        return default

    def __setitem__(self, key: Any, value: Any) -> None:
        nkey = self._normalize_key(key)
        if len(nkey) != len(self._matrix.axes):
            raise ModelError(
                f"matrix {self._matrix._name!r}: expected "
                f"{len(self._matrix.axes)} indices, got {len(nkey)}"
            )
        self._overrides[nkey] = value


def matrix(*axes: Dim | Periods, default: Any = None) -> Matrix:
    """Declare a parameter table indexed by one or more axes."""
    return Matrix(*axes, default=default)


class Glob:
    """A named global parameter exposed as ``self.<name>`` on a Model.

    Implemented as a descriptor so that attribute access yields the underlying
    value (or an instance-level override stored in ``model._globs``).
    """

    def __init__(self, default: Any, doc: str | None = None) -> None:
        self.default = default
        self.doc = doc
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        overrides: dict[str, Any] = obj.__dict__.get("_glob_overrides", {})
        if self._name in overrides:
            return overrides[self._name]
        return self.default

    def __set__(self, obj: Any, value: Any) -> None:
        obj.__dict__.setdefault("_glob_overrides", {})[self._name] = value


def glob(default: Any, doc: str | None = None) -> Any:
    """Declare a global parameter on a Model class.

    Returns a descriptor. The annotation type is ``Any`` so that
    ``growth_rate = glob(0.02)`` and ``self.growth_rate`` are seen as compatible
    types (the value, not the descriptor).
    """
    return Glob(default, doc)


class Row:
    """Descriptor for an ``@row`` method.

    On bound access (``self.budget``) returns a :class:`BoundRow` callable that
    caches per ``(row_name, *idx)`` in the owning model's cell cache. ``idx``
    is the tuple of axis values (typically ``(t,)`` for a 1-D row, or
    ``(p, r, t)`` for a multi-dim row declared with ``@row(over=[...])``).
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        over: Sequence[Dim | Periods] | None = None,
    ) -> None:
        self.fn = fn
        self.name: str = fn.__name__
        self.over: tuple[Dim | Periods, ...] | None = tuple(over) if over else None
        self.explicit_deps: set[str] | None = None  # set by Layer-2 sugar

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return BoundRow(self, obj)


class BoundRow:
    """Bound callable for a row on a specific Model instance."""

    __slots__ = ("instance", "row")

    def __init__(self, row: Row, instance: Any) -> None:
        self.row = row
        self.instance = instance

    def __call__(self, *idx: Any) -> Any:
        cells: dict[tuple[Any, ...], Any] = self.instance._cells
        key: tuple[Any, ...] = (self.row.name, *idx) if len(idx) != 1 else (self.row.name, idx[0])
        if key in cells:
            return cells[key]
        computing: set[tuple[Any, ...]] = self.instance._computing
        if key in computing:
            chain = " -> ".join(repr(c) for c in computing) + f" -> {key!r}"
            raise CircularReferenceError(f"Circular reference detected: {chain}")
        computing.add(key)
        try:
            value = self.row.fn(self.instance, *idx)
        finally:
            computing.discard(key)
        cells[key] = value
        return value


def row(
    fn: Callable[..., Any] | None = None,
    *,
    over: Sequence[Dim | Periods] | None = None,
) -> Any:
    """Mark a method as a row in the DAG.

    Two forms:
      ``@row`` — single-axis (the model's ``time``).
      ``@row(over=[products, regions, time])`` — multi-dim row.
    """
    if fn is None:

        def _wrap(f: Callable[..., Any]) -> Any:
            return Row(f, over=over)

        return _wrap
    return Row(fn, over=over)


class Scalar:
    """Descriptor for an ``@scalar`` method.

    A scalar row produces a single value (no period axis). It still participates
    in the DAG with full caching: bound access returns the value directly.
    """

    def __init__(self, fn: Callable[..., Any]) -> None:
        self.fn = fn
        self.name: str = fn.__name__
        self.explicit_deps: set[str] | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        cells: dict[tuple[str, Any], Any] = obj._cells
        key = (self.name, None)
        if key in cells:
            return cells[key]
        computing: set[tuple[str, Any]] = obj._computing
        if key in computing:
            chain = " -> ".join(f"{n}[{p}]" for n, p in computing) + f" -> {self.name}[]"
            raise CircularReferenceError(f"Circular reference detected: {chain}")
        computing.add(key)
        try:
            value = self.fn(obj)
        finally:
            computing.discard(key)
        cells[key] = value
        return value


def scalar(fn: Callable[..., Any]) -> Any:
    """Mark a method as a scalar row in the DAG.

    A scalar row takes only ``self`` and returns a single value::

        @scalar
        def npv(self):
            return xl.npv(self.discount_rate, self.series("cash_flow"))

    Scalar rows are first-class DAG nodes (PRD §3.5).
    """
    return Scalar(fn)


class Depends:
    """Descriptor for a cross-model dependency declared via :func:`depends`.

    On bound access (``self.costs``) it returns a *solved* instance of the
    upstream model, lazily constructed and cached on the dependent model
    instance.
    """

    def __init__(self, upstream: type[Model]) -> None:
        self.upstream = upstream
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        cache: dict[str, Model] = obj.__dict__.setdefault("_depends_cache", {})
        if self._name not in cache:
            instance = self.upstream()
            instance.solve()
            cache[self._name] = instance
        return cache[self._name]


def depends(upstream: type[Model]) -> Any:
    """Declare a dependency on another :class:`Model` (PRD §3.8).

    Usage::

        class PnL(Model):
            costs = depends(Costs)

            @row
            def margin(self, t):
                return self.revenue(t) - self.costs.total_cost(t)

    Circularity across models is detected at solve time.
    """
    if not isinstance(upstream, type) or not issubclass(upstream, Model):
        raise TypeError(f"depends() expects a Model subclass, got {upstream!r}")
    return Depends(upstream)


# ---------------------------------------------------------------------------
# Model base class
# ---------------------------------------------------------------------------


class Model:
    """Base class for user-defined models.

    Subclasses declare:
      - exactly one period axis: ``time = periods(start, end)``
      - zero or more globals: ``growth_rate = glob(0.05)``
      - one or more rows: ``@row def budget(self, t): ...``

    Phase 0 supports a single period axis and Layer-1 row signatures only.
    """

    # Populated by __init_subclass__:
    _rows: ClassVar[dict[str, Row]] = {}
    _scalars: ClassVar[dict[str, Scalar]] = {}
    _globs: ClassVar[dict[str, Glob]] = {}
    _periods_attrs: ClassVar[dict[str, Periods]] = {}
    _dims: ClassVar[dict[str, Dim]] = {}
    _matrices: ClassVar[dict[str, Matrix]] = {}
    _depends: ClassVar[dict[str, Depends]] = {}

    _sugar: ClassVar[bool] = True

    def __init_subclass__(cls, *, sugar: bool | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if sugar is not None:
            cls._sugar = sugar
        rows: dict[str, Row] = {}
        scalars: dict[str, Scalar] = {}
        globs: dict[str, Glob] = {}
        periods_attrs: dict[str, Periods] = {}
        dims: dict[str, Dim] = {}
        matrices: dict[str, Matrix] = {}
        deps: dict[str, Depends] = {}
        for name, attr in cls.__dict__.items():
            if isinstance(attr, Row):
                rows[name] = attr
            elif isinstance(attr, Scalar):
                scalars[name] = attr
            elif isinstance(attr, Glob):
                globs[name] = attr
            elif isinstance(attr, Periods):
                periods_attrs[name] = attr
            elif isinstance(attr, Dim):
                dims[name] = attr
            elif isinstance(attr, Matrix):
                matrices[name] = attr
            elif isinstance(attr, Depends):
                deps[name] = attr
        for base in cls.__mro__[1:]:
            if base is Model or base is object:
                continue
            for name, attr in vars(base).items():
                if isinstance(attr, Row) and name not in rows:
                    rows[name] = attr
                elif isinstance(attr, Scalar) and name not in scalars:
                    scalars[name] = attr
                elif isinstance(attr, Glob) and name not in globs:
                    globs[name] = attr
                elif isinstance(attr, Periods) and name not in periods_attrs:
                    periods_attrs[name] = attr
                elif isinstance(attr, Dim) and name not in dims:
                    dims[name] = attr
                elif isinstance(attr, Matrix) and name not in matrices:
                    matrices[name] = attr
                elif isinstance(attr, Depends) and name not in deps:
                    deps[name] = attr
        cls._rows = rows
        cls._scalars = scalars
        cls._globs = globs
        cls._periods_attrs = periods_attrs
        cls._dims = dims
        cls._matrices = matrices
        cls._depends = deps
        _check_cross_model_cycle(cls)
        if cls._sugar:
            from .sugar import desugar_class

            desugar_class(cls)

    def __init__(self) -> None:
        self._cells: dict[tuple[str, Any], Any] = {}
        self._computing: set[tuple[str, Any]] = set()

    # -- inspection --------------------------------------------------------

    @property
    def time(self) -> Periods:
        """Return the single period axis defined on the class.

        Phase 0 enforces exactly one ``periods(...)`` attribute. The attribute
        name is conventionally ``time`` but any name works.
        """
        if not self._periods_attrs:
            raise ModelError(f"{type(self).__name__} has no periods(...) axis")
        if len(self._periods_attrs) > 1:
            names = ", ".join(self._periods_attrs)
            raise ModelError(
                f"Phase 0 supports a single period axis; got: {names}"
            )
        return next(iter(self._periods_attrs.values()))

    def row_names(self) -> list[str]:
        """Return the names of all rows declared on this model."""
        return list(self._rows)

    def cells(self) -> dict[tuple[str, Any], Any]:
        """Return a copy of the computed cell map."""
        return dict(self._cells)

    def cell(self, row_name: str, period: Any) -> Any:
        """Return the value at ``(row_name, *idx)``; raises if not computed.

        For multi-dim rows, pass a tuple: ``model.cell("revenue", (p, r, t))``.
        For single-dim rows, pass the period directly: ``model.cell("budget", 2024)``.
        """
        key = (row_name, *period) if isinstance(period, tuple) else (row_name, period)
        return self._cells[key]

    def has_cell(self, row_name: str, period: Any) -> bool:
        key = (row_name, *period) if isinstance(period, tuple) else (row_name, period)
        return key in self._cells

    def series(self, row_name: str) -> list[Any]:
        """Return the series of values for a row across all periods."""
        if row_name not in self._rows:
            raise ModelError(f"Unknown row: {row_name}")
        r = type(self)._rows[row_name]
        if r.over is not None:
            return [self._cells[(row_name, *idx)] for idx in _product(*r.over)]
        return [self._cells[(row_name, t)] for t in self.time]

    # -- display (Phase 3) -------------------------------------------------

    def format_table(self) -> str:
        """Render the solved model as a column-aligned text table.

        Rows x periods grid; scalars (if any) print as ``name = value``
        lines after a blank separator. Single-periods-axis only.
        """
        self._check_displayable()
        periods_list = list(self.time)
        formatted: list[tuple[str, list[str]]] = []
        for name, r in type(self)._rows.items():
            formatted.extend(_expand_row_for_display(self._cells, name, r, periods_list))
        name_w = max((len(n) for n in self._rows), default=1)
        col_widths = [
            max([len(str(t)), *(len(vals[i]) for _, vals in formatted)])
            for i, t in enumerate(periods_list)
        ]
        lines: list[str] = []
        header = " " * name_w + "  " + "  ".join(
            str(t).rjust(w) for t, w in zip(periods_list, col_widths, strict=True)
        )
        lines.append(header)
        for name, vals in formatted:
            lines.append(
                name.ljust(name_w)
                + "  "
                + "  ".join(v.rjust(w) for v, w in zip(vals, col_widths, strict=True))
            )
        if self._scalars:
            lines.append("")
            for sname in self._scalars:
                lines.append(f"{sname} = {_fmt_value(self._cells.get((sname, None)))}")
        return "\n".join(lines)

    def format_csv(self) -> str:
        """Render the solved model as CSV (rows x periods, then scalars)."""
        import csv
        import io

        self._check_displayable()
        periods_list = list(self.time)
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["", *(str(t) for t in periods_list)])
        for name, r in type(self)._rows.items():
            for label, vals in _expand_row_for_display(self._cells, name, r, periods_list):
                w.writerow([label, *vals])
        if self._scalars:
            w.writerow([])
            for sname in self._scalars:
                w.writerow([sname, self._cells.get((sname, None))])
        return buf.getvalue()

    def _check_displayable(self) -> None:
        if not self._cells:
            raise ModelError(
                f"{type(self).__name__} not solved yet. Call .solve() first."
            )
        if not self._periods_attrs:
            raise ModelError(
                f"{type(self).__name__} has no periods(...) axis to display."
            )
        if len(self._periods_attrs) > 1:
            raise ModelError(
                "Display supports a single period axis; "
                f"got: {', '.join(self._periods_attrs)}"
            )

    def __str__(self) -> str:
        if not self._cells:
            return f"<{type(self).__name__}: not solved>"
        return self.format_table()

    def __repr__(self) -> str:
        state = "solved" if self._cells else "not solved"
        n_rows = len(self._rows)
        n_cells = len(self._cells)
        return (
            f"<{type(self).__name__}: "
            f"{n_rows} row{'s' if n_rows != 1 else ''}, "
            f"{n_cells} cell{'s' if n_cells != 1 else ''}, {state}>"
        )

    # -- solving -----------------------------------------------------------

    def solve(self) -> Model:
        """Solve the model eagerly via topological evaluation."""
        from .solver import eager_solve

        eager_solve(self)
        return self


def _fmt_value(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e16:
            return str(int(v))
        return f"{v:.6g}"
    return str(v)


def _expand_row_for_display(
    cells: dict[tuple[Any, ...], Any],
    name: str,
    r: "Row",
    periods_list: list[Any],
) -> list[tuple[str, list[str]]]:
    """Return display sub-rows for a row, expanding non-time axes into separate lines."""
    if r.over is None:
        return [(name, [_fmt_value(cells.get((name, t))) for t in periods_list])]

    # Find the Periods axis position so time stays on columns.
    time_pos = next((i for i, a in enumerate(r.over) if isinstance(a, Periods)), None)
    if time_pos is None:
        return [(name, [_fmt_value(None)] * len(periods_list))]

    other_axes = [a for i, a in enumerate(r.over) if i != time_pos]
    result: list[tuple[str, list[str]]] = []
    combos = list(_product(*other_axes)) if other_axes else [()]
    for combo in combos:
        label = f"{name}[{','.join(str(c) for c in combo)}]" if combo else name
        vals: list[str] = []
        for t in periods_list:
            idx: list[Any] = list(combo)
            idx.insert(time_pos, t)
            vals.append(_fmt_value(cells.get((name, *idx))))
        result.append((label, vals))
    return result


def _check_cross_model_cycle(cls: type[Model]) -> None:
    """Detect circular ``depends()`` chains at class-definition time."""
    seen: set[type[Model]] = set()

    def visit(target: type[Model], path: tuple[type[Model], ...]) -> None:
        if target in path:
            chain = " -> ".join(c.__name__ for c in (*path, target))
            raise ModelError(f"Circular cross-model dependency: {chain}")
        if target in seen:
            return
        seen.add(target)
        for dep in target._depends.values():
            visit(dep.upstream, (*path, target))

    visit(cls, ())
