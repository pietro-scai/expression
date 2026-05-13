import { gateway } from "@ai-sdk/gateway";
import { streamText } from "ai";

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    messages,
    model: gateway("anthropic/claude-sonnet-4.6"),
    system: "You are a helpful assistant.",
  });

  return result.toUIMessageStreamResponse();
}
