import { auth } from "@clerk/nextjs/server";
import { desc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { models } from "@/lib/db/schema";

export async function GET() {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const rows = await db
    .select({
      id: models.id,
      name: models.name,
      version: models.version,
      updatedAt: models.updatedAt,
    })
    .from(models)
    .where(eq(models.userId, userId))
    .orderBy(desc(models.updatedAt))
    .limit(50);

  return Response.json(rows);
}
