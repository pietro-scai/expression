# model — Codex plugin

Spreadsheet-as-DAG modeling skills for the
[`model`](https://github.com/pcasella/amsterdam) CLI, packaged for
[Codex](https://developers.openai.com/codex).

## What's inside

- **Skills** — the same eight skills shipped in the Claude Code plugin,
  pulled from the canonical source at `src/expression/skills/` in the main
  repo.

The Codex plugin is intentionally lighter than the Claude Code one: no
extra slash commands and no MCP server in v1. Codex's bash-equivalent
calls into the `expression` CLI directly. We will revisit MCP in v2 if the
ergonomics turn out worse than Claude Code's.

## Install (local dev)

```bash
# 1. install the framework on PATH (the plugin shells out to it)
cd /absolute/path/to/amsterdam
uv pip install -e .

# 2. populate plugins/codex/{skills,reference}/
make plugins
```

Then register the plugin with Codex following its current local-plugin
convention (Codex's mechanism mirrors Claude Code's marketplace-based
flow; check `codex /plugin help` for the exact verbs in your version).
The manifest lives at `plugins/codex/.codex-plugin/plugin.json`.

In any `expression` workspace:

```
codex
> Use the bottom-up-modeling skill to forecast SaaS revenue.
```

See `docs/PLUGINS.md` in the main repo for the full install/dev guide.
