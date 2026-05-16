import { getActiveSandboxId, stopSandbox } from "@/lib/agent";
import { Sandbox } from "@vercel/sandbox";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const sandboxId = searchParams.get("id");

  if (sandboxId) {
    try {
      const sandbox = await Sandbox.get({ sandboxId });
      return Response.json({ sandboxId: sandbox.sandboxId, status: sandbox.status });
    } catch {
      return Response.json({ sandboxId: null, status: "gone" });
    }
  }

  return Response.json({ sandboxId: getActiveSandboxId() });
}

export async function DELETE() {
  await stopSandbox();
  return Response.json({ ok: true });
}
