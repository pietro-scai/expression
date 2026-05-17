"""``expression doc sync`` — reconcile ``expression.md`` with ``expression.py`` (PRD §6).

Phase 3 ships a *report-only* sync: it identifies drift between the rows
declared in code and the rows mentioned in the markdown spec. Interactive
reconciliation (the agent walking the user through the fixes) is part of
the agent loop in :mod:`model.agent`; this module is the primitive both
the CLI command and the agent reuse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .core import Model

# Match ``identifier`` inside backticks, optionally with ``[period]`` suffix:
# `budget`, `budget[2024]`, `budget[year]`. We intentionally don't try to
# parse prose — backtick-mention is the contract.
_BACKTICK_NAME = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\[[^`\]]*\])?`")


def extract_md_mentions(md_text: str) -> set[str]:
    """Return identifiers mentioned in the markdown via backtick quotes."""
    return {m.group(1) for m in _BACKTICK_NAME.finditer(md_text)}


@dataclass(frozen=True)
class DocDrift:
    """Drift between code rows/scalars and ``expression.md`` mentions."""

    in_code_not_md: list[str]
    in_md_not_code: list[str]  # mentioned in md but not a row/scalar/glob
    code_symbols: list[str]

    @property
    def empty(self) -> bool:
        return not (self.in_code_not_md or self.in_md_not_code)


def compare(model: Model, md_text: str) -> DocDrift:
    """Compare a model's symbols to the names mentioned in its markdown."""
    rows = set(model._rows)  # pyright: ignore[reportPrivateUsage]
    scalars = set(model._scalars)  # pyright: ignore[reportPrivateUsage]
    globs = set(model._globs)  # pyright: ignore[reportPrivateUsage]
    code_symbols = rows | scalars | globs
    documented = code_symbols & extract_md_mentions(md_text)
    in_code_not_md = sorted(code_symbols - documented)

    # We can't reliably tell what's a row reference vs. an English word in
    # code-fences, so only flag mentions that *look* like row references —
    # i.e. ``name[...]`` form. Bare ``cogs`` could be a typo or just prose.
    period_re = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)\[[^`\]]+\]`")
    period_mentions = {m.group(1) for m in period_re.finditer(md_text)}
    in_md_not_code = sorted(period_mentions - code_symbols)

    return DocDrift(
        in_code_not_md=in_code_not_md,
        in_md_not_code=in_md_not_code,
        code_symbols=sorted(code_symbols),
    )


def format_drift(drift: DocDrift) -> str:
    if drift.empty:
        return "✓ expression.md is in sync with expression.py"
    lines: list[str] = []
    if drift.in_code_not_md:
        lines.append(
            f"# In code but not in expression.md ({len(drift.in_code_not_md)})"
        )
        for name in drift.in_code_not_md:
            lines.append(f"  - {name}")
    if drift.in_md_not_code:
        lines.append(
            f"# Mentioned in expression.md but not in code "
            f"({len(drift.in_md_not_code)})"
        )
        for name in drift.in_md_not_code:
            lines.append(f"  - {name}")
    return "\n".join(lines)
