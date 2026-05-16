---
name: parameter-elicitation
description: Surface 2-5 globals the user will most likely tweak. Promote them.
---

When designing or importing a model, ask the user:

> "Which 2-5 numbers do you most expect to tweak when running scenarios?"

These become "key parameters". For each:

- Declare as a `glob(...)` with a clear `doc=` string.
- Place at the top of the class, above any rows.
- Mention by name in `model.md` under **Inputs**.
- Suggest a parameter-sweep test in `tests/` (PRD §10.4).

Don't elicit more than 5 — the goal is the small handful the user actually
tweaks, not an exhaustive list.
