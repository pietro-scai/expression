---
name: override-discipline
description: Hardcoded one-off values belong in overrides.toml, not in formulas.
---

If you spot a magic number patched into a row's formula (e.g. `if t == 2023:
return 150 else …`), **stop and convert it** to an override:

```
model overrides add <row> <period> <value> --reason "<why>"
```

Then remove the special case from the formula. The row stays clean; the
override is data, versioned in `overrides.toml`, with a reason field.

Refuse the inverse: never bake an override back into a formula "to clean up
the toml file". Overrides are auditable; rewritten formulas erase the
audit trail.
