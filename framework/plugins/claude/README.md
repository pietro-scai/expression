# model — Claude Code plugin

Spreadsheet-as-DAG modeling skills and slash commands for the
[`model`](https://github.com/pcasella/amsterdam) CLI, packaged for
[Claude Code](https://code.claude.com).

## What's inside

- **Skills** (`/sweet:<skill-name>`) — eight skills covering bottom-up
  modeling, parameter elicitation, override discipline, circularity
  resolution, Excel fidelity, the import flow, the small-step iteration
  loop, and the harness adapter contract.
- **Slash commands** — `/sweet:run`, `/sweet:diff`, `/sweet:show`,
  `/sweet:explain`, `/sweet:export`, each a thin wrapper around the
  corresponding `sweet` CLI command.

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
/plugin install sweet@sweet-dev
```

Then in any `sweet` workspace:

```
/sweet:bottom-up-modeling
"Forecast SaaS revenue with 5% monthly churn."
```

See `docs/PLUGINS.md` in the main repo for the full install/dev guide and
the slash-command catalogue.
