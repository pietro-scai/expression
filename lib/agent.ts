import { ToolLoopAgent } from "ai";
import { gateway } from "@ai-sdk/gateway";
import { Sandbox } from "@vercel/sandbox";
import path from "path";
import fs from "fs/promises";
import {
  createBashTool,
  createUpdateModelTool,
  createRunModelTool,
  createRenderChartTool,
} from "./tools";

// Hobby plan hard cap is 2,700,000 ms (45 min). Pro/Enterprise allow up to 5 h.
const SANDBOX_TIMEOUT_MS = 45 * 60 * 1000;
// Push the deadline forward on every request (capped at plan max by the API).
const EXTEND_BY_MS = 20 * 60 * 1000;

interface AgentState {
  agent: ToolLoopAgent;
  sandbox: Sandbox;
  sandboxId: string;
}

let agentState: AgentState | null = null;
let agentPromise: Promise<AgentState> | null = null;

// Snapshot of the provisioned environment — survives warm restarts so cold starts
// after a timeout skip the 1–2 min provisioning and boot in seconds instead.
let cachedSnapshotId: string | null = null;

export function getActiveSandboxId(): string | null {
  return agentState?.sandboxId ?? null;
}

export function getActiveSnapshotId(): string | null {
  return cachedSnapshotId;
}

/** Extend the running sandbox's deadline on every user request. */
export async function extendSandboxTimeout(): Promise<void> {
  if (!agentState) return;
  try {
    await agentState.sandbox.extendTimeout(EXTEND_BY_MS);
  } catch {
    // Sandbox already gone — tools will detect and surface it.
  }
}

/** Called by tools when they catch a 410 / StreamError. */
export function markSandboxGone(): void {
  agentState = null;
  agentPromise = null;
}

/** Gracefully stop the current sandbox and clear state. */
export async function stopSandbox(): Promise<void> {
  const state = agentState;
  agentState = null;
  agentPromise = null;
  if (state) {
    try {
      await state.sandbox.stop();
    } catch {
      // Already gone — ignore.
    }
  }
}

export function getAgent(
  preferredSandboxId: string | null,
  preferredSnapshotId?: string | null
): Promise<ToolLoopAgent> {
  // Warm path: client confirms the exact sandbox we have cached.
  if (preferredSandboxId && agentState?.sandboxId === preferredSandboxId) {
    return Promise.resolve(agentState.agent);
  }

  // In-flight init, no preference — ride it out rather than double-provision.
  if (!preferredSandboxId && agentPromise && !agentState) {
    return agentPromise.then((s) => s.agent);
  }

  // Seed module-level snapshot cache from the client's persisted store.
  if (preferredSnapshotId && !cachedSnapshotId) {
    cachedSnapshotId = preferredSnapshotId;
  }

  agentState = null;
  agentPromise = initAgent(preferredSandboxId ?? undefined)
    .then((state) => {
      agentState = state;
      return state;
    })
    .catch((err) => {
      agentPromise = null;
      agentState = null;
      throw err;
    });

  return agentPromise.then((s) => s.agent);
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

async function initAgent(resumeSandboxId?: string): Promise<AgentState> {
  let sandbox: Sandbox;

  if (resumeSandboxId) {
    try {
      // Reconnect to the still-running sandbox.
      sandbox = await Sandbox.get({ sandboxId: resumeSandboxId });
      // Push the deadline forward immediately so the reconnected sandbox
      // doesn't expire in the middle of this session.
      await sandbox.extendTimeout(EXTEND_BY_MS);
    } catch {
      // Sandbox gone (410) — fast-start from snapshot if we have one.
      sandbox = await bootSandbox();
    }
  } else {
    sandbox = await bootSandbox();
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tools: Record<string, any> = {
    update_model: createUpdateModelTool(sandbox, markSandboxGone),
    run_model: createRunModelTool(sandbox, markSandboxGone),
    bash: createBashTool(sandbox, markSandboxGone),
    render_chart: createRenderChartTool(),
  };

  const agent = new ToolLoopAgent({
    model: gateway("anthropic/claude-sonnet-4-6"),
    tools,
    providerOptions: {
      anthropic: {
        thinking: { type: "enabled", budgetTokens: 8000 },
      },
    },
    instructions: `You are a sweet model builder — a collaborative assistant that helps users create financial and analytical models using the sweet Python DSL.

sweet models are Python classes that inherit from Model and define:
- time = periods(start_year, end_year)  — integer years ONLY, e.g. periods(2024, 2029)
- glob(default, doc="...")              — named scalar inputs / assumptions
- @row functions                        — computed rows, one value per period
- dim([...])                            — categorical axes for multi-dimensional rows

STRICT TYPE RULES — violating these causes a runtime error:
1. periods() takes TWO INTEGERS (years). Never pass strings like "2025-01".
   CORRECT:   time = periods(2025, 2030)
   WRONG:     time = periods("2025-01", "2025-12")  ← crashes

2. Use bare @row only for one-dimensional time rows. For multi-dimensional rows,
   declare every axis explicitly with @row(over=[...]) and make the function
   parameters match that order exactly.
   CORRECT:
       products = dim(["A", "B"])
       time = periods(2025, 2030)
       @row(over=[time, products])
       def revenue(self, t, products):
           return ...
   WRONG:
       @row
       def revenue(self, t, products): ...  ← crashes; solver passes only t
   WRONG:  @row(doc="...")  ← crashes

3. All globs MUST have doc=:  seed = glob(100, doc="Starting value ($K)")

4. Prefer Layer-2 sugar for @row bodies — no self/t boilerplate, cleaner formulas.
   A @row with NO arguments triggers sugar; a @row with (self, t) is Layer-1 (fallback).
   PREFERRED (Layer 2):
       @row
       def revenue():
           """Annual revenue ($M)."""
           revenue[first] = seed               # bare glob, 'first' → time.first
           revenue[n]     = revenue[n-1] * (1 + growth_rate)  # n-1 lag, bare glob
   Layer-2 reference:
   - name[first] / name[last]  → boundary period
   - name[n]  / name[n-k]      → current / lagged value (k = any integer)
   - Bare names resolve to model attrs automatically (globs, rows) — no self. needed
   - name[:]  → full series list;  name[a:b]  → inclusive window list
   For @rows that must call cross-model data, use Layer-1 (self, t):
       @row
       def gross_income(self, t):
           return self.salary.total_comp(t) + self.other_income
   Multi-dimensional rows currently use Layer-1 with @row(over=[...]), not
   Layer-2 sugar.

5. Always name depends() at class level — never call it inline inside a @row body.
   Accessing self.<dep_name> on an instance returns the solved upstream Model directly.
   CORRECT:
       salary   = depends(SalaryModel)
       expenses = depends(ExpensesModel)
       ...
       @row
       def gross_income(self, t):
           return self.salary.total_comp(t) + self.other_income
   WRONG:  return depends(SalaryModel).total_comp(t) + ...         ← inline depends()
   WRONG:  return self.salary.upstream().total_comp(t) + ...       ← .upstream() does not exist

6. A single sweet.py can contain multiple Model subclasses. sweet run discovers all of them,
   auto-resolves their dependency order via depends(), and solves them all.
   Circular cross-model deps raise a clear error.

7. Avoid optional heavy Python dependencies inside model formulas unless already installed
   in /tmp/sweet-venv. The default sandbox installs sweet's core deps only
   (networkx, openpyxl, typer). Prefer stdlib implementations for small helpers
   like IRR/root finding, or explicitly install the package before relying on it.

WORKFLOW
1. Ask the user what to model: business question, time horizon, key drivers, outputs.
2. Call update_model with a minimal skeleton (periods + 1-2 globs + 1 row).
3. Inspect the returned snapshots immediately:
   - Check execution.status — it must be "ok" before you respond to the user.
   - If status is "error", fix the code and call update_model again in the same turn.
   - Never leave the model in a failing or un-run state when replying.
4. Iterate on every subsequent change the same way:
   - ANY edit to the model → call update_model → mandatory, no exceptions.
   - update_model automatically runs sweet describe AND sweet run and streams both
     the model definition and the solved results to the panel.
   - Verify the returned snapshots (structure + values) before responding.
   - Do NOT call run_model after update_model — the run is already included.
5. use run_model ONLY when re-running without any code change
   (e.g., user asks to recalculate with different glob values you've already set).

TOOL RETURN VALUES
update_model and run_model return ModelSnapshot[]. Each snapshot has:
- snapshot.definition  — the describe output (rows, globs, dag). Always present on success.
- snapshot.execution   — the run output (status, tables, scalars). Present when run succeeds.
Always read these fields to confirm the model is correct before replying.

SANDBOX ERRORS
If a tool returns { sandboxGone: true }, the sandbox has timed out.
Tell the user: "The sandbox has timed out. Please click **Reinitiate sandbox** in the toolbar — a fresh environment will be ready in a few seconds."
Do NOT attempt any further tool calls after a sandbox timeout.

BASH TOOL
- Runs via \`bash -c\` so ALL shell features work: pipes, redirects, &&, ||, globs, subshells.
- A non-zero exitCode means the command failed — it does NOT mean the sandbox is gone.
  Only act on sandbox death when the tool returns { sandboxGone: true }.
- Pre-installed: git, gh, ripgrep (rg), fd, jq, yq, fzf, bat, eza, tree, git-delta, direnv, brew
- Python 3.11 venv: /tmp/sweet-venv/bin/python
- Model file: workspace/sweet.py  |  Outputs: workspace/outputs/

After sandbox reinitiation the workspace is reset to empty. When the user asks to continue,
call update_model to re-establish the current model from conversation history — it will
describe and run automatically, confirming the fresh environment is correct.

The panel updates automatically on every update_model / run_model call — don't narrate the numbers back.

CHARTS
- Call render_chart ONLY after a successful run_model or update_model — never before there is solved data.
- Do NOT use bash to prepare chart data. Read values directly from the execution results already in this conversation.
- Build the data array yourself from the tables in the last execution result; pass it in the render_chart call.
- Choose chartType wisely: "line" for time-series trends, "bar" for period-over-period comparisons, "area" for cumulative or stacked quantities.
- Keep series focused: 1-4 series per chart. If there are many rows, chart the most interesting ones.
- The xKey should be the period (year). Each series key must exactly match a key in the data objects.
- Only call render_chart when it adds genuine insight — not on every model run.`,
  });

  return { agent, sandbox, sandboxId: sandbox.sandboxId };
}

/**
 * Boot a sandbox as fast as possible.
 * - Fast path: create from the cached provisioned snapshot (seconds).
 * - Slow path: full provision + snapshot so next boot is fast.
 */
async function bootSandbox(): Promise<Sandbox> {
  if (cachedSnapshotId) {
    try {
      return await Sandbox.create({
        source: { type: "snapshot", snapshotId: cachedSnapshotId },
        timeout: SANDBOX_TIMEOUT_MS,
      });
    } catch {
      // Snapshot expired or invalid — fall through to full provision.
      cachedSnapshotId = null;
    }
  }

  // Slow path: provision fresh then snapshot so future boots are fast.
  // Needs a long timeout because brew install takes 10-15 min.
  const temp = await Sandbox.create({ timeout: 45 * 60 * 1000 });
  await provisionSandbox(temp);

  // snapshot() stops the temp sandbox automatically.
  const snapshot = await temp.snapshot({ expiration: 0 }); // never expire
  cachedSnapshotId = snapshot.snapshotId;

  // Boot the real agent sandbox from the fresh snapshot.
  return await Sandbox.create({
    source: { type: "snapshot", snapshotId: cachedSnapshotId },
    timeout: SANDBOX_TIMEOUT_MS,
  });
}

async function provisionSandbox(sbx: Sandbox): Promise<void> {
  const frameworkDir = path.join(process.cwd(), "framework");
  const files = await collectFiles(frameworkDir, "framework");

  const setupScript = `#!/bin/bash
set -e

# ── Python / sweet ──────────────────────────────────────────────────────────
python3 -m ensurepip --upgrade 2>/dev/null || true
python3 -m pip install --quiet uv
python3 -m uv python install 3.11
python3 -m uv venv --python 3.11 /tmp/sweet-venv
python3 -m uv pip install --quiet --python /tmp/sweet-venv/bin/python 'networkx>=3.2' 'openpyxl>=3.1' 'typer>=0.12'
SITE=$(/tmp/sweet-venv/bin/python -c 'import site; print(site.getsitepackages()[0])')
echo "$(pwd)/framework/src" > "$SITE/sweet.pth"

# ── System prereqs for Homebrew ─────────────────────────────────────────────
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq build-essential procps curl file git sudo locales 2>/dev/null || true

# ── Homebrew ─────────────────────────────────────────────────────────────────
# Brew refuses to run as root; create a dedicated user when needed.
if [ "$(id -u)" = "0" ]; then
  id -u linuxbrew &>/dev/null || useradd -m -s /bin/bash linuxbrew
  echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/linuxbrew
  chmod 440 /etc/sudoers.d/linuxbrew
  RUN_AS_BREW='su - linuxbrew -c'
  BREW_BIN=/home/linuxbrew/.linuxbrew/bin/brew
else
  RUN_AS_BREW='bash -c'
  BREW_BIN="$HOME/.linuxbrew/bin/brew"
fi

$RUN_AS_BREW 'NONINTERACTIVE=1 bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' || true

# Install requested packages (watchman may fail on some images — allow it)
$RUN_AS_BREW "$BREW_BIN install gh ripgrep fd jq yq fzf bat eza tree git-delta direnv" || true
$RUN_AS_BREW "$BREW_BIN install watchman" || true

# Symlink brew + all its binaries into /usr/local/bin so root's PATH sees them
if [ "$(id -u)" = "0" ]; then
  ln -sf "$BREW_BIN" /usr/local/bin/brew 2>/dev/null || true
  for bin in /home/linuxbrew/.linuxbrew/bin/*; do
    ln -sf "$bin" "/usr/local/bin/$(basename "$bin")" 2>/dev/null || true
  done
fi

echo done`;

  await sbx.writeFiles([
    ...files,
    { path: "workspace/sweet.py", content: "" },
    { path: "workspace/outputs/.keep", content: "" },
    { path: "setup.sh", content: setupScript },
  ]);

  const result = await sbx.runCommand("bash", ["setup.sh"]);
  const [, stderr] = await Promise.all([result.stdout(), result.stderr()]);
  if (result.exitCode !== 0) {
    throw new Error(`Sandbox provisioning failed: ${stderr}`);
  }
}

async function collectFiles(
  dir: string,
  prefix: string
): Promise<{ path: string; content: Buffer }[]> {
  const SKIP = new Set([
    "__pycache__",
    ".git",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    "node_modules",
  ]);
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files: { path: string; content: Buffer }[] = [];

  for (const entry of entries) {
    if (SKIP.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    const sandboxPath = `${prefix}/${entry.name}`;

    if (entry.isDirectory()) {
      files.push(...(await collectFiles(fullPath, sandboxPath)));
    } else if (entry.isFile()) {
      files.push({ path: sandboxPath, content: await fs.readFile(fullPath) });
    }
  }

  return files;
}
