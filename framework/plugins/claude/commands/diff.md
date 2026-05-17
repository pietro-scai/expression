---
description: Show the cell-level diff against the accepted snapshot.
---

Run `expression diff` in the workspace and present the result.

- If there is no snapshot yet, tell the user to run `/expression:run` then
  `expression snapshot accept` first.
- If the diff is empty, say so in one line — no extra commentary.
- If the diff is non-empty, group changes by row and call out any cell
  whose sign flipped or magnitude moved by >50%.
