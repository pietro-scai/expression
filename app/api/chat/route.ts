import { auth } from "@clerk/nextjs/server";
import { and, eq } from "drizzle-orm";
import { after } from "next/server";
import { convertToModelMessages } from "ai";
import {
  getAgent,
  getActiveSandboxId,
  getActiveSnapshotId,
  extendSandboxTimeout,
} from "@/lib/agent";
import { db } from "@/lib/db";
import { conversations, messages, models, modelVersions } from "@/lib/db/schema";
import type { ModelSnapshot } from "@/lib/model-types";

function deriveTitle(msgs: { role: string; content?: unknown; parts?: unknown[] }[]): string {
  const userMsg = msgs.findLast((m) => m.role === "user");
  if (!userMsg) return "New conversation";
  const text =
    typeof userMsg.content === "string"
      ? userMsg.content
      : (userMsg.parts as { type: string; text?: string }[] | undefined)
          ?.find((p) => p.type === "text")?.text ?? "";
  return text.slice(0, 60) || "New conversation";
}

export async function POST(req: Request) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { messages: msgs, sandboxId, snapshotId, conversationId: incomingConvId } = await req.json();

  // Resolve or create conversation
  let conversationId: string = incomingConvId ?? "";
  if (!conversationId) {
    const title = deriveTitle(msgs);
    const [conv] = await db
      .insert(conversations)
      .values({ userId, title })
      .returning({ id: conversations.id });
    conversationId = conv.id;
  }

  await extendSandboxTimeout();

  // Build the per-request model save closure
  const saveModel = async (snapshots: ModelSnapshot[]) => {
    const snap = snapshots.find((s) => s.execution?.status === "ok" && s.source);
    if (!snap) return;

    const name = snap.source.match(/^class\s+(\w+)\s*\(/m)?.[1] ?? "Untitled";

    const existing = await db
      .select()
      .from(models)
      .where(and(eq(models.userId, userId), eq(models.name, name)))
      .limit(1);

    if (existing.length > 0) {
      const model = existing[0];
      await db.insert(modelVersions).values({
        modelId: model.id,
        version: model.version,
        source: model.source,
        modelJson: model.modelJson,
        resultJson: model.resultJson,
      });
      await db
        .update(models)
        .set({
          source: snap.source,
          modelJson: snap.definition ?? null,
          resultJson: snap.execution ?? null,
          version: model.version + 1,
          updatedAt: new Date(),
        })
        .where(eq(models.id, model.id));
      await db
        .update(conversations)
        .set({ modelId: model.id, updatedAt: new Date() })
        .where(eq(conversations.id, conversationId));
    } else {
      const [newModel] = await db
        .insert(models)
        .values({
          userId,
          name,
          source: snap.source,
          modelJson: snap.definition ?? null,
          resultJson: snap.execution ?? null,
          version: 1,
        })
        .returning({ id: models.id });
      await db
        .update(conversations)
        .set({ modelId: newModel.id, updatedAt: new Date() })
        .where(eq(conversations.id, conversationId));
    }
  };

  const agent = await getAgent(sandboxId ?? null, snapshotId ?? null, {
    userId,
    conversationId,
    saveModel,
  });

  const result = await agent.stream({
    messages: await convertToModelMessages(msgs),
  });

  const activeSandboxId = getActiveSandboxId();
  const activeSnapshotId = getActiveSnapshotId();

  // Capture the user-message timestamp now so the assistant message's createdAt
  // is always strictly later, even if both after() callbacks race to the DB.
  const userMsgCreatedAt = new Date();

  // Save user message immediately (non-blocking)
  after(async () => {
    const userMsg = msgs[msgs.length - 1];
    if (userMsg?.role === "user") {
      const parts = Array.isArray(userMsg.parts)
        ? userMsg.parts
        : typeof userMsg.content === "string"
          ? [{ type: "text", text: userMsg.content }]
          : [];
      await db
        .insert(messages)
        .values({ conversationId, role: "user", parts, createdAt: userMsgCreatedAt })
        .catch(() => {});
    }
  });

  // Save assistant message server-side when stream completes — works even if the
  // user navigates away mid-stream, closes the tab, or switches conversations.
  const streamResponse = result.toUIMessageStreamResponse({
    onFinish: ({ messages: uiMessages }) => {
      const assistant = uiMessages.findLast((m) => m.role === "assistant");
      if (!assistant) return;
      // Use a timestamp guaranteed to be after userMsgCreatedAt.
      const assistantCreatedAt = new Date(userMsgCreatedAt.getTime() + 1);
      after(
        db
          .insert(messages)
          .values({ conversationId, role: "assistant", parts: assistant.parts as object[], createdAt: assistantCreatedAt })
          .then(() =>
            db
              .update(conversations)
              .set({ updatedAt: new Date() })
              .where(eq(conversations.id, conversationId))
          )
          .catch(() => {})
      );
    },
  });

  return new Response(streamResponse.body, {
    status: streamResponse.status,
    headers: {
      ...Object.fromEntries(streamResponse.headers.entries()),
      ...(activeSandboxId ? { "x-sandbox-id": activeSandboxId } : {}),
      ...(activeSnapshotId ? { "x-snapshot-id": activeSnapshotId } : {}),
      "x-conversation-id": conversationId,
    },
  });
}
