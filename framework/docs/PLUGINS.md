# Plugins — Claude Code & Codex

`model` ships its skills and slash commands as plugins for the two CLI agent
hosts most of our users already live in: **Claude Code** and **Codex**.
Plugins are the supported way to drive `model` from an LLM agent.

The plugins are self-contained: each one bundles the modeling skills, a
framework operator-manual skill (`expression-framework`), and the long-form
reference documents (`SPECIFICATION.md`, `DOCS.md`) so that the in-host
agent has everything it needs without reading anything from the framework
checkout.

This document covers what's in the plugins, how the source-of-truth sync
works, how to install each plugin in dev, and how distribution is laid out.

---
## §0 Quick start claude

```bash
cd examples
claude --plugin-dir ../plugins/claude

```



## §1 — Repo layout & build

There is one canonical copy of every skill and reference on disk.
Everything inside `plugins/{claude,codex}/{skills,reference}/` is derived.

```
amsterdam/
  src/expression/skills/                  # SOURCE OF TRUTH (nine skills)
    bottom-up-modeling/SKILL.md
    circularity-resolution/SKILL.md
    excel-fidelity/SKILL.md
    harness-adapter/SKILL.md
    import-excel/SKILL.md
    expression-framework/SKILL.md         # discipline + CLI surface + workspace conventions
    override-discipline/SKILL.md
    parameter-elicitation/SKILL.md
    small-step-iteration/SKILL.md
  SPECIFICATION.md                   # bundled into each plugin as reference/SPECIFICATION.md
  docs/DOCS.md                       # bundled into each plugin as reference/DOCS.md

  plugins/
    claude/
      .claude-plugin/plugin.json     # Claude Code manifest
      commands/                      # /expression:run, /expression:diff, …
      skills/                        # ← materialised from src/expression/skills/
      reference/                     # ← SPECIFICATION.md + DOCS.md, bundled
    codex/
      .codex-plugin/plugin.json      # Codex manifest
      skills/                        # ← materialised from src/expression/skills/
      reference/                     # ← SPECIFICATION.md + DOCS.md, bundled
    shared/
      skills-link.sh                 # the sync script (link | copy)

  Makefile                           # `make plugins`
```

`plugins/{claude,codex}/{skills,reference}/` is **never edited by hand**.
Both directories are wiped and re-populated by
`plugins/shared/skills-link.sh` from `src/expression/skills/` and the top-level
docs.

### Two sync modes

```bash
make plugins         # symlinks  — dev loop, edits to src/model/skills propagate live
make plugins-copy    # plain copies — for self-contained release tarballs
make plugins-clean   # remove plugins/{claude,codex}/{skills,reference} entirely
```

The plugins layer is additive: nothing in the existing `expression` CLI is
modified. Both plugins read the same skills directory the framework's
internal loader reads, so editing a `SKILL.md` once changes both
distribution endpoints after the next `make plugins`.

### Manifest fields

Both manifests are minimal and parallel: `name`, `version`, `description`,
`author`, `repository`, `homepage`, `license`, `keywords`. Schemas:

- Claude Code — <https://code.claude.com/docs/en/plugins-reference>
- Codex — <https://developers.openai.com/codex/plugins/build>

The plugin name `expression` becomes the prefix for slash commands and skills in
Claude Code (`/expression:bottom-up-modeling`, `/expression:run`, …).

### Self-containment

A user who installs the plugin into their host **does not need a checkout
of this repo** to use it. Two pieces make that work:

- **`expression-framework` skill** — the framework's operator manual, written
  for an LLM. Embeds the discipline rules (small-step, override-discipline,
  leaves-first), the CLI surface, workspace conventions, exit-code
  semantics, and pointers into `reference/`. Lives at
  `src/expression/skills/expression-framework/SKILL.md` and is propagated by
  `make plugins`.
- **`reference/` bundle** — `SPECIFICATION.md` (formal spec) and
  `docs/DOCS.md` (long-form tutorial) are mirrored into each plugin under
  `plugins/{claude,codex}/reference/`. The `expression-framework` skill points
  the in-host agent at these files when it needs authoritative answers.

The user still installs the `expression` CLI separately (`uv tool install
model`), because the plugin shells out to it. Everything else — the
discipline, the CLI vocabulary, the spec — travels inside the plugin.

---

## §2 — Claude Code: install & dev loop

Claude Code resolves plugins through a **marketplace registry** at
`~/.claude/plugins/known_marketplaces.json`. `make dev-install` writes
that entry, symlinks all nine skills into `~/.claude/skills/`, and wires
up the marketplace structure — no manual JSON editing needed.

### One-time prerequisites (in your shell)

```bash
# 1. install the framework on PATH (slash commands shell out to it)
cd /absolute/path/to/amsterdam
uv pip install -e .

# 2. install skills + marketplace into Claude Code
make dev-install
```

### Install in Claude Code (inside the `claude` REPL)

```
/plugin install expression@expression-dev
```

After install you should see:
- Nine skills available (loaded automatically when relevant based on their
  `description` field): `bottom-up-modeling`, `expression-framework`, etc.
- Slash commands prefixed `/expression:` — `/expression:run`, `/expression:diff`,
  `/expression:show`, `/expression:explain`, `/expression:export`.

The `expression-framework` skill carries the discipline rules + CLI surface;
the eight content skills layer specific guidance on top. The
`expression-framework` skill also bundles `references/SPECIFICATION.md` and
`references/DOCS.md` so the agent can read them directly.

### Dev iteration

The right amount of teardown depends on what changed.

**1. Skill or command body changed** — symlinks mean the new content is
already on disk. Just reload:

```
/plugin reload
```

No reinstall needed.

**2. Manifest or plugin structure changed** (`plugin.json`, new command
file, etc.):

```
/plugin uninstall expression
/plugin install expression@expression-dev
```

**3. Nuclear (clean state from scratch)**:

```bash
# in your shell:
make dev-uninstall
make dev-install
```

```
# in Claude Code:
/plugin uninstall expression
/plugin install expression@expression-dev
```

### Uninstall

```bash
# shell — removes skills, marketplace entry, known_marketplaces.json entry
make dev-uninstall
```

```
# Claude Code — removes the installed plugin
/plugin uninstall expression
```

Run both. The shell step cleans up the filesystem; the Claude Code step
clears its internal state.

### Inspecting what's installed

```
/plugin list                # plugins currently active
/plugin marketplace list    # registered marketplaces
```

### Smoke test

```bash
mkdir /tmp/saas-budget && cd /tmp/saas-budget
expression init .
claude
```

```
/plugin install expression@expression-dev
/expression:run
> Walk me through the bottom-up-modeling skill and add a churn row.
```

If `/expression:run` solves the model and `/expression:diff` shows a meaningful
delta after a tweak, the plugin works.

---

## §3 — Slash commands catalogue

`plugins/claude/commands/` holds thin markdown wrappers around the most
common `expression` CLI invocations. Each file is a Claude Code slash-command:
the body instructs Claude what to do, and Claude calls the framework via
its `Bash` tool.

| Command | Wraps | Purpose |
|---|---|---|
| `/expression:run` | `expression run` | Solve the workspace and print the row table; report deltas vs the last snapshot. |
| `/expression:diff` | `expression diff` | Show the cell-level diff against the accepted snapshot. |
| `/expression:show` | `expression show <cell>` | Inspect one cell's value and provenance. |
| `/expression:explain` | `expression explain <cell>` | Walk a cell's dependency tree and show the formula path. |
| `/expression:export` | `expression export` | Round-trip the model out to `.xlsx`. |

Slash-commands are deliberately small. Anything that needs judgment lives
in a skill, which the agent loads when relevant; commands exist to give
the user a single keystroke for the actions they invoke ten times an hour.

---

## §4 — Modeler subagent (deferred)

The plan reserves `plugins/claude/agents/modeler.md` for a subagent the
user can switch into via `/agents` to lock the host into "modeler mode"
for a session.

**Status: not shipped in v1.** The `expression-framework` skill plus the
content skills appear sufficient; revisit only if the host's default
behaviour drifts away from the small-step / leaves-first discipline.

---

## §5 — Codex: install & dev loop

Codex's plugin format mirrors Claude Code's closely enough that the same
skills directory and reference bundle work unchanged. The manifest lives
at `plugins/codex/.codex-plugin/plugin.json`.

```bash
make plugins                                # populates plugins/codex/{skills,reference}/ too
codex --plugin-dir /absolute/path/to/amsterdam/plugins/codex
```

### MCP server (deferred)

The plan leaves room for a `.mcp.json` exposing `expression run/show/diff/…`
as MCP tools, in case Codex's bash-tool ergonomics turn out worse than
Claude Code's. **Not shipped in v1** — re-evaluate after dogfooding.

---

## §6 — Distribution

For Phase 1 we ship via `--plugin-dir` against a checkout. Public
distribution comes after a friend has installed locally and run through
`expression init` → `expression run` → tweak → `expression run` without rough edges.

When that lands:

- **Claude Code** — submit at <https://claude.ai/settings/plugins/submit>;
  the marketplace catalog file is `plugins/marketplace/claude.json`.
- **Codex** — submit per <https://developers.openai.com/codex/plugins/build>;
  the catalog file is `plugins/marketplace/codex.json`.

Both catalog files are checked in so the submission is reproducible from
the repo, not from a one-off form.
