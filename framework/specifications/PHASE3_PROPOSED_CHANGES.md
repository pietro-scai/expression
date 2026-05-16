# Phase 3 — Proposed changes / clarifications to SPECIFICATION.md

Same convention as the earlier phase docs. This slice ships the Phase 3
items beyond display primitives (covered in PHASE2.1):

- skills directory + skill loader
- `model agent` interactive loop with **pluggable harnesses**
- `model doc sync` for `model.md` reconciliation
- `model diff` and `model snapshot accept`
- trace logging to `.model/trace/`

> Status legend: **[decision]** = chose one path; **[deviation]** =
> differs from PRD as written; **[question]** = needs your call.

Builds on Phase 0 (#1-11), Phase 1 (#12-25), Phase 2 (#26-40), Phase 2.1
(#41-47). Numbers continue from there.

---

## 48. Harness is pluggable; default is the Anthropic API [decision]

The PRD says the agent loop "drives Claude Code/Codex" but doesn't pin
the architecture. We split the loop from the harness:

- `src/model/agent/loop.py` — owns the conversation, tool dispatch, and
  trace logging. Provider-agnostic.
- `src/model/agent/harness.py` — protocol every backend implements.
- `src/model/agent/harnesses/anthropic_api.py` — built-in, **default**.
- `src/model/agent/harnesses/claude_code.py` — shells out to `claude`.

Adding a third backend (OpenAI, an internal gateway) is one new module
that calls `register_harness("name", Factory)`. The
`harness-adapter` skill (`src/model/skills/harness-adapter/SKILL.md`)
documents the contract with a working template.

Why default to the API and not Claude Code? `model agent` runs as the
"engine" inside CI, scripts, and other agents — needing an interactive
GUI tool installed locally is the wrong default. Users who want their
edit history in Claude Code's session memory pass `--harness=claude-code`.

## 49. `ANTHROPIC_API_KEY` is the single source of API credentials [decision]

The Anthropic harness reads `ANTHROPIC_API_KEY` from the environment via
the SDK's default behavior. Two tiny additions on top:

- A clear actionable error if the variable is missing (with the URL to
  the console and the exact `export` line to run).
- A clear actionable error if the SDK isn't installed
  (`pip install anthropic` or `uv add anthropic`).

The skill bundle in the system prompt also calls this out so the agent
itself can guide users who hit it. No alternative auth paths (config
file, keyring, etc.) — a single env var is enough for v1.

## 50. Tool surface is intentionally narrow [decision]

The Anthropic harness exposes three tools to the model:

- `read_file(path)` — auto-approved (read-only).
- `write_file(path, content)` — gated on user confirmation.
- `run_model(subcommand, args)` — gated on user confirmation; allowlist
  of `model` subcommands only.

No general `bash` tool. Reasoning: the iteration loop is
edit → run → diff → test → commit, all of which `model` already covers.
Bash brings sandbox-escape concerns the PRD doesn't ask us to solve.

Bypass with `--yes` if you want headless runs (CI, scripted experiments).

## 51. Conversation owns tool dispatch, not the harness [decision]

The harness returns tool *calls*. The loop dispatches them, runs the
confirmation prompt, writes the result to the trace, and feeds it back
on the next turn. This means:

- A new harness doesn't have to re-implement file I/O, command running,
  or audit logging.
- Switching between Anthropic API and a local LLM doesn't change the
  tool semantics.
- The trace is authoritative — every action the agent took is in
  `.model/trace/<session>.jsonl`.

## 52. `model doc sync` is report-only in v1 [decision]

PRD §6 calls for "interactive" reconciliation. Phase 3 ships the
foundation: parse `model.md`, compare backtick-quoted identifiers to
the rows/scalars/globs declared in code, report drift in both
directions. Exit code 1 if drift exists (so CI can gate on it).

Interactive reconciliation lives inside `model agent` — the agent reads
the drift, asks the user, and edits `model.md`. That's a richer
workflow than a single CLI prompt would deliver.

## 53. Snapshots are separate from `outputs/result.json` [decision]

`model run` writes `outputs/result.json` on every run (always). The
*committed* snapshot is `.model/snapshot.json`, updated only by
`model snapshot accept`. `model diff` compares current solve to the
committed snapshot.

Two files instead of one because they have different lifecycles:
`result.json` is the latest output, snapshot is the reviewed checkpoint.
Conflating them would re-introduce the silent-drift bug PRD §10.2 is
trying to prevent.

## 54. Diff tolerance is exact, not relative [decision]

`model diff` compares values with `!=`. No `--tol` flag. Reasoning:
solve is deterministic. A drift of `1e-15` is a red flag worth
surfacing, not noise to suppress. If false positives become a nuisance
(e.g. when a model legitimately depends on platform float ordering),
add `--tol` then; don't bury it in the default.

## 55. Trace is JSON Lines, not a SQLite log [decision]

`.model/trace/<session>.jsonl` — one JSON record per line. No `structlog`
dependency, no schema migrations. Cheap to grep, easy to load into
pandas/duckdb/etc., compatible with any structured-log viewer.

Each session is one agent run. Filename includes the start timestamp so
consecutive runs don't clobber.

## 56. Skills are markdown files, loaded at startup [decision]

Skills live under `src/model/skills/<skill-name>/SKILL.md` following
Anthropic's convention (YAML frontmatter, markdown body). The loader
reads every directory at startup and concatenates the bodies into the
system prompt.

This means **no Python changes are needed to add or edit a skill** —
edit the markdown, restart the loop. Custom skills can be loaded from
any directory by passing a different `skills_dir` to `LoopConfig`
(useful for project-specific rules layered on top of the bundled set).

The bundled skills cover PRD §8.1 (`bottom-up-modeling`,
`small-step-iteration`, `parameter-elicitation`,
`circularity-resolution`, `override-discipline`, `excel-fidelity`,
`import-excel`) plus a `harness-adapter` skill that documents how to
plug in new backends.

## 57. System prompt is cached via Anthropic prompt cache [decision]

The system prompt — agent rules + all loaded skills + current workspace
snapshot — is marked `cache_control: ephemeral` on the Anthropic
harness. Re-runs within the 5-minute cache TTL skip re-billing the long
prefix (~90% cost reduction on input tokens once warm).

Other harnesses are free to ignore `system` caching; nothing in the
loop depends on it.

---

## Out of scope for this Phase 3 slice (intentionally)

- Multi-scenario `model run --scenario=...` (open question #3 in PRD §15).
- Property-based tests via `hypothesis` (PRD §10.3 marks this as
  "encouraged, not required").
- Web viewer for `model.md` + result preview (Phase 4 candidate).
- `model agent` triggering full git commits from inside the loop. The
  loop *can* call `model run/test`, but commits stay manual — too easy
  to accidentally commit a half-finished change.
- Fancy diff renderers (deepdiff, etc.). Plain `key: a → b` is enough
  to read at the terminal.

---

## Open follow-ups for Pietro

1. **Skill versioning.** As skills evolve, will we want
   per-skill semver and a way to pin? Probably overkill until we ship
   skills as a package; defer.
2. **Per-project custom skills.** A `<workspace>/.model/skills/`
   directory that layers on top of the bundled set. Wired through the
   `LoopConfig` plumbing already; just needs a CLI flag and docs.
3. **Streaming responses.** The Anthropic SDK supports streaming; the
   harness currently uses the synchronous `messages.create`. Streaming
   makes long replies feel faster but complicates the trace
   (line-buffered vs. full-message). Defer until users ask.
4. **Token-budget guardrails.** The loop currently has `max_turns=50`
   but no token cap. A long session could rack up cost surprisingly.
   Add a `--max-cost` flag once the usage data shows it matters.
5. **Tool allowlist customization.** Right now the allowlist of `model`
   subcommands is hard-coded. A plug-in tool registry (similar to the
   harness registry) would let projects add e.g. `git_commit`, but
   that's a real surface-area expansion — wait until needed.
