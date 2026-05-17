"""``xl`` — Excel-flavored function library for use inside ``@row`` / ``@scalar``.

Plain Python: every function takes arrays/scalars in, returns arrays/scalars out.
The DSL doesn't introspect this module — call sites are just function calls.

Phase 1 covers the common cases enumerated in PRD §3.5. Anything missing can be
added by users via :func:`register`.
"""

from __future__ import annotations

import builtins
import math
import statistics
from collections.abc import Callable, Iterable, Sequence
from datetime import date, timedelta
from typing import Any

# Save builtin references so xl.sum / xl.min / xl.max can shadow without recursion.
_b_sum = builtins.sum
_b_min = builtins.min
_b_max = builtins.max

Number = float | int

# ---------------------------------------------------------------------------
# Statistical
# ---------------------------------------------------------------------------


def sum(values: Iterable[Number]) -> float:
    return float(_b_sum(values))


def avg(values: Iterable[Number]) -> float:
    seq = list(values)
    return float(_b_sum(seq)) / len(seq)


def min(values: Iterable[Number]) -> float:
    return float(_b_min(values))


def max(values: Iterable[Number]) -> float:
    return float(_b_max(values))


def stdev(values: Iterable[Number]) -> float:
    return float(statistics.pstdev(values))


def var(values: Iterable[Number]) -> float:
    return float(statistics.pvariance(values))


def median(values: Iterable[Number]) -> float:
    return float(statistics.median(values))


def percentile(values: Iterable[Number], p: float) -> float:
    """Linear-interpolation percentile (Excel ``PERCENTILE.INC`` semantics)."""
    seq = sorted(float(v) for v in values)
    if not seq:
        raise ValueError("percentile of empty sequence")
    if not 0 <= p <= 1:
        raise ValueError(f"percentile p must be in [0,1], got {p}")
    n = len(seq)
    if n == 1:
        return seq[0]
    rank = p * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return seq[lo]
    return seq[lo] + (seq[hi] - seq[lo]) * (rank - lo)


# ---------------------------------------------------------------------------
# Logical
# ---------------------------------------------------------------------------


def if_(cond: Any, when_true: Any, when_false: Any) -> Any:
    return when_true if cond else when_false


def and_(*xs: Any) -> bool:
    return all(xs)


def or_(*xs: Any) -> bool:
    return any(xs)


def not_(x: Any) -> bool:
    return not x


def iferror(thunk: Callable[[], Any], fallback: Any) -> Any:
    """Excel ``IFERROR``-ish: evaluate thunk; on any exception, return fallback."""
    try:
        return thunk()
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------


def npv(rate: float, cash_flows: Sequence[Number]) -> float:
    """Net present value at ``rate``.

    Convention: cash flow at index 0 is discounted by one period (matches Excel
    ``NPV``). For an "investment-at-time-0" convention, callers should pass
    ``cash_flow[0] + xl.npv(rate, cash_flow[1:])``.
    """
    return float(_b_sum(cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cash_flows)))


def xnpv(rate: float, cash_flows: Sequence[Number], dates: Sequence[date]) -> float:
    if len(cash_flows) != len(dates):
        raise ValueError("xnpv: cash_flows and dates must have the same length")
    d0 = dates[0]
    return float(
        _b_sum(
            cf / (1 + rate) ** ((d - d0).days / 365.0)
            for cf, d in zip(cash_flows, dates, strict=True)
        )
    )


def irr(cash_flows: Sequence[Number], guess: float = 0.1, tol: float = 1e-9) -> float:
    """Internal rate of return: Newton's method, then bisection fallback."""
    cf = [float(x) for x in cash_flows]
    if not cf or all(x == 0 for x in cf):
        raise ValueError("irr: empty or all-zero cash flows")

    def f(r: float) -> float:
        return _b_sum(c / (1 + r) ** i for i, c in enumerate(cf))

    def fprime(r: float) -> float:
        return _b_sum(-i * c / (1 + r) ** (i + 1) for i, c in enumerate(cf))

    r = guess
    for _ in range(100):
        try:
            v = f(r)
            d = fprime(r)
        except (ZeroDivisionError, OverflowError):
            break
        if d == 0:
            break
        new_r = r - v / d
        if abs(new_r - r) < tol:
            return new_r
        r = new_r

    lo, hi = -0.999, 10.0
    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        raise ValueError("irr: no sign change in bracket [-0.999, 10.0]")
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def xirr(
    cash_flows: Sequence[Number], dates: Sequence[date], guess: float = 0.1, tol: float = 1e-9
) -> float:
    if len(cash_flows) != len(dates):
        raise ValueError("xirr: cash_flows and dates must have the same length")
    d0 = dates[0]

    def f(r: float) -> float:
        return _b_sum(
            cf / (1 + r) ** ((d - d0).days / 365.0)
            for cf, d in zip(cash_flows, dates, strict=True)
        )

    lo, hi = -0.999, 10.0
    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        return guess
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def mirr(cash_flows: Sequence[Number], finance_rate: float, reinvest_rate: float) -> float:
    cf = [float(x) for x in cash_flows]
    n = len(cf) - 1
    if n <= 0:
        raise ValueError("mirr: need at least 2 cash flows")
    pv_neg = _b_sum(c / (1 + finance_rate) ** i for i, c in enumerate(cf) if c < 0)
    fv_pos = _b_sum(c * (1 + reinvest_rate) ** (n - i) for i, c in enumerate(cf) if c > 0)
    if pv_neg == 0:
        raise ValueError("mirr: no negative cash flows")
    return (fv_pos / -pv_neg) ** (1 / n) - 1


def pmt(rate: float, nper: int, pv: float, fv: float = 0.0, when: int = 0) -> float:
    """Excel PMT. ``when``: 0=end of period (default), 1=start."""
    if rate == 0:
        return -(pv + fv) / nper
    f = (1 + rate) ** nper
    return -(pv * f + fv) * rate / ((f - 1) * (1 + rate * when))


def pv(rate: float, nper: int, pmt_: float, fv: float = 0.0, when: int = 0) -> float:
    if rate == 0:
        return -(pmt_ * nper + fv)
    f = (1 + rate) ** nper
    return -(pmt_ * (1 + rate * when) * (f - 1) / rate + fv) / f


def fv(rate: float, nper: int, pmt_: float, pv_: float = 0.0, when: int = 0) -> float:
    if rate == 0:
        return -(pv_ + pmt_ * nper)
    f = (1 + rate) ** nper
    return -(pv_ * f + pmt_ * (1 + rate * when) * (f - 1) / rate)


def rate(
    nper: int,
    pmt_: float,
    pv_: float,
    fv_: float = 0.0,
    when: int = 0,
    guess: float = 0.1,
    tol: float = 1e-9,
) -> float:
    def f(r: float) -> float:
        if r == 0:
            return pv_ + pmt_ * nper + fv_
        fac = (1 + r) ** nper
        return pv_ * fac + pmt_ * (1 + r * when) * (fac - 1) / r + fv_

    lo, hi = -0.999, 10.0
    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        return guess
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def nper(rate_: float, pmt_: float, pv_: float, fv_: float = 0.0, when: int = 0) -> float:
    if rate_ == 0:
        return -(pv_ + fv_) / pmt_
    factor = pmt_ * (1 + rate_ * when) / rate_
    num = factor - fv_
    den = pv_ + factor
    if num / den <= 0:
        raise ValueError("nper: arguments imply impossible loan/investment")
    return math.log(num / den) / math.log(1 + rate_)


# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------


def eomonth(d: date, months: int) -> date:
    """Last day of month, ``months`` away from ``d`` (negative = past)."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1) - timedelta(days=1)


def edate(d: date, months: int) -> date:
    """Same day-of-month, shifted by ``months`` (clamps to month length)."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = eomonth(date(y, m, 1), 0).day
    return date(y, m, _b_min(d.day, last_day))


def yearfrac(start: date, end: date) -> float:
    """Actual/365 day-count fraction (Excel basis 3)."""
    return (end - start).days / 365.0


def workday(d: date, days: int) -> date:
    """Add business days (Mon-Fri) skipping weekends."""
    direction = 1 if days >= 0 else -1
    remaining = abs(days)
    cur = d
    while remaining > 0:
        cur = cur + timedelta(days=direction)
        if cur.weekday() < 5:
            remaining -= 1
    return cur


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


def cumsum(values: Iterable[Number]) -> list[float]:
    out: list[float] = []
    running = 0.0
    for v in values:
        running += float(v)
        out.append(running)
    return out


def running_max(values: Iterable[Number]) -> list[float]:
    out: list[float] = []
    cur = -math.inf
    for v in values:
        cur = _b_max(cur, float(v))
        out.append(cur)
    return out


def drawdown(values: Iterable[Number]) -> list[float]:
    """Peak-to-trough drawdowns, expressed as negative fractions of the peak."""
    out: list[float] = []
    peak = -math.inf
    for v in values:
        fv = float(v)
        if fv > peak:
            peak = fv
        out.append((fv - peak) / peak if peak > 0 else 0.0)
    return out


def first_where(values: Sequence[Any], pred: Callable[[Any], bool]) -> int | None:
    """Return the *index* (0-based) of the first element matching ``pred``.

    For period-aware lookup callers can map index→period via the model's
    ``time`` axis. (Phase 1 keeps this index-based — period mapping is a layer
    above this primitive.)
    """
    for i, v in enumerate(values):
        if pred(v):
            return i
    return None


def last_where(values: Sequence[Any], pred: Callable[[Any], bool]) -> int | None:
    last_idx: int | None = None
    for i, v in enumerate(values):
        if pred(v):
            last_idx = i
    return last_idx


# ---------------------------------------------------------------------------
# Lookup (operate on datasets/matrices — actual table types implement .lookup)
# ---------------------------------------------------------------------------


def vlookup(table: Any, key: Any, column: str) -> Any:
    """Look up ``key`` in ``table``'s index and return ``column``."""
    return table.lookup(key, column)


def index_match(table: Any, key: Any, column: str) -> Any:
    return vlookup(table, key, column)


def xlookup(table: Any, key: Any, column: str, default: Any = None) -> Any:
    try:
        return table.lookup(key, column)
    except (KeyError, IndexError):
        return default


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


_registry: dict[str, Callable[..., Any]] = {}


def register(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Add a function to the ``xl`` namespace.

    Usage::

        @xl.register
        def sharpe(returns, risk_free=0.02):
            ...
        # then xl.sharpe(...) anywhere
    """
    name = fn.__name__
    _registry[name] = fn
    globals()[name] = fn
    return fn
