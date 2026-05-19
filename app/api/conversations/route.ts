import { auth } from "@clerk/nextjs/server";
import { desc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { conversations, models } from "@/lib/db/schema";

export async function GET() {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const rows = await db
    .select({
      id: conversations.id,
      title: conversations.title,
      modelName: models.name,
      updatedAt: conversations.updatedAt,
    })
    .from(conversations)
    .leftJoin(models, eq(conversations.modelId, models.id))
    .where(eq(conversations.userId, userId))
    .orderBy(desc(conversations.updatedAt))
    .limit(50);

  return Response.json(rows);
}

export async function POST(req: Request) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { title } = await req.json().catch(() => ({}));

  const [conv] = await db
    .insert(conversations)
    .values({ userId, title: title ?? null })
    .returning({ id: conversations.id });

  return Response.json({ id: conv.id });
}
