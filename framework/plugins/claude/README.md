# model — Claude Code plugin

Spreadsheet-as-DAG modeling skills and slash commands for the
[`model`](https://github.com/pcasella/amsterdam) CLI, packaged for
[Claude Code](https://code.claude.com).

## What's inside

- **Skills** (`/expression:<skill-name>`) — eight skills covering bottom-up
  modeling, parameter elicitation, override discipline, circularity
  resolution, Excel fidelity, the import flow, the small-step iteration
  loop, and the harness adapter contract.
- **Slash commands** — `/expression:run`, `/expression:diff`, `/expression:show`,
  `/expression:explain`, `/expression:export`, each a thin wrapper around the
  corresponding `expression` CLI command.

## Install (local dev)

```bash
# 1. install the framework on PATH (the plugin shells out to it)
cd /absolute/path/to/amsterdam
uv pip install -e .

# 2. install skills + marketplace into Claude Code
make dev-install
```

Inside the `claude` REPL:

```
/plugin install expression@expression-dev
```

Then in any `expression` workspace:

```
/expression:bottom-up-modeling
"Forecast SaaS revenue with 5% monthly churn."
```

See `docs/PLUGINS.md` in the main repo for the full install/dev guide and
the slash-command catalogue.
