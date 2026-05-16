import {
  getAgent,
  getActiveSandboxId,
  getActiveSnapshotId,
  extendSandboxTimeout,
} from "@/lib/agent";
import { convertToModelMessages } from "ai";

export async function POST(req: Request) {
  const { messages, sandboxId, snapshotId } = await req.json();

  // Push the sandbox deadline forward on every user message so the sandbox
  // only times out when the user is genuinely idle, not mid-conversation.
  await extendSandboxTimeout();

  const agent = await getAgent(sandboxId ?? null, snapshotId ?? null);
  const result = await agent.stream({
    messages: await convertToModelMessages(messages),
  });

  const streamResponse = result.toUIMessageStreamResponse();
  const activeSandboxId = getActiveSandboxId();
  const activeSnapshotId = getActiveSnapshotId();

  return new Response(streamResponse.body, {
    status: streamResponse.status,
    headers: {
      ...Object.fromEntries(streamResponse.headers.entries()),
      ...(activeSandboxId ? { "x-sandbox-id": activeSandboxId } : {}),
      ...(activeSnapshotId ? { "x-snapshot-id": activeSnapshotId } : {}),
    },
  });
}
