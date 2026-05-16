import { z } from "zod";
import { APIError, type Sandbox, StreamError } from "@vercel/sandbox";
import type { ModelSnapshot } from "./model-types";

function isSandboxGone(err: unknown): boolean {
  if (err instanceof APIError) return err.response.status === 410;
  if (err instanceof StreamError) return true;
  return false;
}

function sandboxGoneResult(onGone: () => void): { sandboxGone: true; error: string } {
  onGone();
  return { sandboxGone: true as const, error: "Sandbox timed out (HTTP 410)." };
}

const bashInputSchema = z.object({
  command: z
    .string()
    .describe(
      "Full bash command string. Runs via `bash -c`, so pipes, redirects, " +
        "&&, ||, subshells, globs, and all shell features work. " +
        'Example: "find /tmp -name \'*.py\' | xargs grep -l \'import\'"'
    ),
});

export function createBashTool(sandbox: Sandbox, onGone: () => void) {
  return {
    description:
      "Run a shell command in the sandbox. Executes via `bash -c` — pipes, " +
      "redirects, variables, and all bash features are fully supported. " +
      "A non-zero exit code means the command failed, NOT that the sandbox is gone. " +
      "Only treat the sandbox as gone when sandboxGone:true is returned.",
    inputSchema: bashInputSchema,
    execute: async (input: z.infer<typeof bashInputSchema>) => {
      try {
        const result = await sandbox.runCommand("bash", ["-c", input.command]);
        const [stdout, stderr] = await Promise.all([
          result.stdout(),
          result.stderr(),
        ]);
        return { stdout, stderr, exitCode: result.exitCode };
      } catch (err) {
        if (isSandboxGone(err)) return sandboxGoneResult(onGone);
        throw err;
      }
    },
  };
}

async function runCmd(
  sandbox: Sandbox,
  command: string,
  args: string[]
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const result = await sandbox.runCommand(command, args);
  const [stdout, stderr] = await Promise.all([
    result.stdout(),
    result.stderr(),
  ]);
  return { stdout, stderr, exitCode: result.exitCode };
}

async function readFile(sandbox: Sandbox, filePath: string): Promise<string> {
  const { stdout } = await runCmd(sandbox, "cat", [filePath]);
  return stdout;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapDefinition(m: any): ModelSnapshot["definition"] {
  return {
    name: m.model?.name ?? "Model",
    doc: m.model?.doc,
    axes: m.model?.axes ?? {},
    globals: m.inputs ?? {},
    rows: m.tables ?? [],
    scalars: m.scalars ?? [],
    dag: m.model?.dag ?? { nodes: [], edges: [] },
    mermaid: m.model?.mermaid ?? "",
  };
}

async function loadDefinitions(
  sandbox: Sandbox
): Promise<ModelSnapshot["definition"][]> {
  try {
    const json = await readFile(sandbox, "workspace/outputs/model.json");
    const parsed = JSON.parse(json);
    // sweet outputs { models: [{ model: {name,doc,axes}, inputs, tables, scalars }] }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (parsed.models ?? []).map((m: any) => mapDefinition(m));
  } catch {
    return [];
  }
}

export function createUpdateModelTool(sandbox: Sandbox, onGone: () => void) {
  return {
    description:
      "Write the complete sweet.py model file. Automatically runs sweet describe and returns snapshots the UI uses to render all model structures.",
    inputSchema: z.object({
      content: z.string().describe("Complete content for workspace/sweet.py"),
    }),
    execute: async ({
      content,
    }: {
      content: string;
    }): Promise<ModelSnapshot[] | { sandboxGone: true; error: string }> => {
      try {
        await sandbox.writeFiles([{ path: "workspace/sweet.py", content }]);

        const describe = await runCmd(sandbox, "/tmp/sweet-venv/bin/python", [
          "-m", "sweet",
          "describe",
          "--model", "workspace/sweet.py",
        ]);

        if (describe.exitCode !== 0) {
          return [{
            source: content,
            execution: {
              status: "error",
              message: describe.stderr || describe.stdout,
            },
          }];
        }

        const definitions = await loadDefinitions(sandbox);
        return definitions.map((definition) => ({ source: content, definition }));
      } catch (err) {
        if (isSandboxGone(err)) return sandboxGoneResult(onGone);
        throw err;
      }
    },
  };
}

export function createRunModelTool(sandbox: Sandbox, onGone: () => void) {
  return {
    description:
      "Solve the current model with sweet run. Returns execution results (solved values or error) and updates the UI panel.",
    inputSchema: z.object({}),
    execute: async (): Promise<ModelSnapshot[] | { sandboxGone: true; error: string }> => {
      try {
        const source = await readFile(sandbox, "workspace/sweet.py");

        const run = await runCmd(sandbox, "/tmp/sweet-venv/bin/python", [
          "-m", "sweet",
          "run",
          "--model", "workspace/sweet.py",
        ]);

        if (run.exitCode !== 0) {
          return [{
            source,
            execution: {
              status: "error",
              message: run.stderr || run.stdout,
            },
          }];
        }

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        let executionModels: any[] = [];
        try {
          const json = await readFile(sandbox, "workspace/outputs/result.json");
          // result.json has the same { models: [...] } envelope as model.json
          executionModels = JSON.parse(json)?.models ?? [];
        } catch {}

        await runCmd(sandbox, "/tmp/sweet-venv/bin/python", [
          "-m", "sweet",
          "describe",
          "--model", "workspace/sweet.py",
        ]);
        const definitions = await loadDefinitions(sandbox);

        // Zip definitions with per-model execution data by index.
        return definitions.map((definition, i) => {
          const modelData = executionModels[i];
          return {
            source,
            definition,
            execution: {
              status: "ok" as const,
              inputs: modelData?.inputs,
              tables: modelData?.tables,
              scalars: modelData?.scalars,
            },
          };
        });
      } catch (err) {
        if (isSandboxGone(err)) return sandboxGoneResult(onGone);
        throw err;
      }
    },
  };
}
