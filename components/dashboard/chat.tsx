"use client";

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import type { UIMessage } from "ai";
import { SparklesIcon } from "lucide-react";

export function DashboardChat() {
  const { messages, status, stop, sendMessage } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });

  return (
    <div className="flex h-full w-full flex-col">
      <Conversation className="flex-1">
        <ConversationContent>
          {messages.length === 0 ? (
            <ConversationEmptyState
              description="Ask me anything to get started."
              icon={<SparklesIcon className="size-6" />}
              title="How can I help you?"
            />
          ) : (
            messages.map((msg: UIMessage) => (
              <Message from={msg.role} key={msg.id}>
                <MessageContent>
                  {msg.parts.map((part, i) => {
                    if (part.type !== "text") return null;
                    return (
                      <MessageResponse key={i}>{part.text}</MessageResponse>
                    );
                  })}
                </MessageContent>
              </Message>
            ))
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="border-t p-4">
        <PromptInput
          className="mx-auto max-w-3xl"
          onSubmit={({ text }) => {
            if (!text.trim()) return;
            sendMessage({ text });
          }}
        >
          <PromptInputTextarea placeholder="Message..." />
          <PromptInputFooter>
            <PromptInputTools />
            <PromptInputSubmit onStop={stop} status={status} />
          </PromptInputFooter>
        </PromptInput>
      </div>
    </div>
  );
}
