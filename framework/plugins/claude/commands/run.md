---
description: Solve the current model and report the row table.
---

The user wants to solve their `sweet` workspace and see the result.

1. Run `sweet run` from the workspace root using the Bash tool.
2. If the run succeeds, show the row table to the user.
3. If a snapshot exists (`outputs/snapshot.json`), also run `sweet diff` and
   surface any cell-level changes.
4. If the run fails, read the error, point at the offending file/line, and
   suggest the smallest fix that would unblock — do not auto-apply it without
   asking.

Stay quiet on success: the row table speaks for itself.
