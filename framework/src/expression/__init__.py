"""model — Excel-like spreadsheets as Python DAGs."""

from . import dataset, xl
from .core import (
    CircularReferenceError,
    Dim,
    Matrix,
    Model,
    ModelError,
    Periods,
    depends,
    dim,
    glob,
    matrix,
    periods,
    row,
    scalar,
)
from .docsync import DocDrift, format_drift
from .docsync import compare as compare_docs
from .output import describe_model, to_json
from .overrides import (
    Override,
    apply_overrides,
    read_overrides,
    write_overrides,
)
from .snapshot import (
    DiffReport,
    diff_cells,
    format_diff,
    read_snapshot,
    serialize_cells,
    write_snapshot,
)
from .trace import Tracer

register = xl.register

__all__ = [
    "CircularReferenceError",
    "DiffReport",
    "Dim",
    "DocDrift",
    "Matrix",
    "Model",
    "ModelError",
    "Override",
    "Periods",
    "Tracer",
    "apply_overrides",
    "compare_docs",
    "dataset",
    "depends",
    "describe_model",
    "diff_cells",
    "dim",
    "format_diff",
    "format_drift",
    "glob",
    "matrix",
    "periods",
    "read_overrides",
    "read_snapshot",
    "register",
    "row",
    "scalar",
    "serialize_cells",
    "to_json",
    "write_overrides",
    "write_snapshot",
    "xl",
]
