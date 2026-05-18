import { auth } from "@clerk/nextjs/server";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { conversations, messages, models } from "@/lib/db/schema";

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;

  await db
    .delete(conversations)
    .where(and(eq(conversations.id, id), eq(conversations.userId, userId)));

  return new Response(null, { status: 204 });
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;

  const [conv] = await db
    .select()
    .from(conversations)
    .where(and(eq(conversations.id, id), eq(conversations.userId, userId)));

  if (!conv) return new Response("Not found", { status: 404 });

  const [msgs, modelRows] = await Promise.all([
    db
      .select()
      .from(messages)
      .where(eq(messages.conversationId, id))
      .orderBy(asc(messages.createdAt)),
    conv.modelId
      ? db
          .select({
            source: models.source,
            modelJson: models.modelJson,
            resultJson: models.resultJson,
          })
          .from(models)
          .where(eq(models.id, conv.modelId))
          .limit(1)
      : Promise.resolve([]),
  ]);

  return Response.json({
    ...conv,
    messages: msgs,
    model: modelRows[0] ?? null,
  });
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;
  const body = await req.json().catch(() => ({}));

  const allowed: Partial<typeof conversations.$inferInsert> = {};
  if (body.title !== undefined) allowed.title = body.title;
  if (body.sandboxId !== undefined) allowed.sandboxId = body.sandboxId;
  if (body.modelId !== undefined) allowed.modelId = body.modelId;

  await db
    .update(conversations)
    .set({ ...allowed, updatedAt: new Date() })
    .where(and(eq(conversations.id, id), eq(conversations.userId, userId)));

  return Response.json({ ok: true });
}
