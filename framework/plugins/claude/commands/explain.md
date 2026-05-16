---
description: Walk a cell's dependency tree and show the formula path.
---

The user wants to understand how a cell is computed.

1. Run `sweet explain '<cell>'` — quote the argument.
2. Show the dependency tree as returned.
3. If the user asks a follow-up about a specific dependency, run
   `sweet show '<dep>'` to surface its current value.
