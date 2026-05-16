# Phase 4 — Multiple Models in One File

## Motivation

Excel workbooks are multi-sheet. Each sheet is a logical layer: one sheet for salary assumptions, another for the budget, a third for a P&L summary. Users naturally model in layers, and the tool needs to support that idiom without forcing file proliferation.

Previously, `sweet run` enforced exactly **one `Model` subclass per file**. Adding a second class caused an error:

```
✗ Phase 0 expects exactly one Model subclass per file. Found: SalaryModel, BudgetModel
```

This forced users into a multi-file layout even for tightly coupled layers, which is unnecessarily burdensome.

## Decision

Remove the single-model constraint. `sweet run` now:

1. **Discovers** all `Model` subclasses in `sweet.py`.
2. **Builds a cross-model DAG** from `depends()` declarations between models in the same file.
3. **Topologically sorts** the graph — upstream models are solved before downstream ones.
4. **Warns on cycles** — if the cross-model graph has a cycle, exits non-zero with the cycle path.
5. **Solves all models** in sorted order.
6. **Outputs combined results** — `result.json` has the `{"models": [...]}` shape.

## Design choices

### Why `depends()` is still required

`depends()` is the data bridge — it gives a model instance access to another model's solved cells. Without it there's no mechanism for `self.salary.gross(t)` to resolve. The change is not about removing `depends()`; it's about removing the restriction that only one model can exist per file.

What changes: you no longer need to designate a root model or list models in order. `sweet run` infers the order from `depends()` declarations automatically.

### DAG scope: same-file only

The cross-model DAG built for ordering considers only models found in the current `sweet.py`. External models (imported from sister files) are resolved lazily by `Depends.__get__()` as before. This keeps the ordering logic simple: no transitive cross-file graph traversal needed.

### Output shape: always `{"models": [...]}`

The `result.json` top-level structure is now always `{"models": [...]}`, even for single-model files. This is a **breaking change** for consumers that read `result["tables"]` directly instead of `result["models"][0]["tables"]`.

Rationale: a single consistent shape is simpler to consume than a conditional one. The shape was already documented as plural-ready in `output.py`:

```python
# Phase 0 has one per file, but the shape is plural-ready
return {"models": [entry], "documentation": md_text}
```

Migration: update any consumer to use `result["models"][0]` for the first (often only) model.

### Overrides: optional `model` field

`overrides.toml` gains an optional `model` field:

```toml
[[override]]
row    = "raise_rate"
value  = 0.05
model  = "SalaryModel"
reason = "optimistic scenario"
```

Without `model`, the override applies to every model that has a matching row or glob. With it, it is filtered to the named class only.

### Snapshots: `ModelName.` prefix for multi-model

When multiple models are present, `sweet snapshot accept` writes keys prefixed by model class name: `SalaryModel.gross[2025]`. Single-model snapshots retain the flat format `gross[2025]` for backward compatibility.

### `show` command: qualified names

```bash
sweet show 'gross[2025]'             # searches all models
sweet show 'SalaryModel.gross[2025]' # scoped to SalaryModel
```

The qualified form uses the syntax `ModelName.row_name[period]`.

## Error messages

**Circular dependency between models:**

```
✗ Circular dependency between models: SalaryModel -> BudgetModel -> SalaryModel
  Remove the cycle — models in a circular chain cannot be solved.
```

**Circular `depends()` within class definition** (existing behavior, unchanged):

```
ModelError: Circular cross-model dependency: A -> B -> A
```

## What is unchanged

- Layer-1 and Layer-2 DSL syntax — no changes.
- `depends()` syntax — still required for inter-model cell access.
- Multi-file layout — import + `depends()` continues to work.
- Agent loop, skills, harnesses — work identically; the agent sees the combined `result.json`.
- Excel import/export — single-model operations, unchanged.
- `sweet explain` and `sweet doc sync` — operate on the last (root) model in topo order.

## Files changed

| File | Change |
|---|---|
| `src/sweet/cli.py` | `_load_all_models()` replaces `_load_user_model()` as the primary loader; `run`, `show`, `print`, `describe`, `diff`, `snapshot accept`, `overrides add/rm` updated |
| `src/sweet/output.py` | `to_json_multi()` and `describe_models()` added; `describe_model()` becomes a shim |
| `src/sweet/snapshot.py` | `serialize_cells_multi()` added |
| `src/sweet/overrides.py` | `Override` gains `model: str | None` field; `write_overrides` and `read_overrides` updated |
| `tests/test_multimodel.py` | New: 16 test cases |
| `tests/test_phase0.py` | Updated `result.json` access to use `result["models"][0]` |
| `docs/DOCS.md` | New chapter 13 "Multiple models in one file" |
| `specifications/SPECIFICATION.md` | New §3.9 |
| `src/sweet/skills/sweet-framework/SKILL.md` | Updated workspace layout and CLI surface |
