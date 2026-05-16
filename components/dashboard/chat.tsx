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
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import type { ModelSnapshot } from "@/lib/model-types";
import { useSandboxStore } from "@/lib/sandbox-store";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import type { UIMessage } from "ai";
import { RefreshCwIcon, SparklesIcon, Trash2Icon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useModel } from "./model-context";

// Tool names whose output is displayed in the right panel — suppress inline JSON.
const PANEL_TOOLS = new Set(["update_model", "run_model"]);

function getToolName(part: Record<string, unknown>): string {
  if (part.type === "dynamic-tool") return String(part.toolName ?? "");
  const type = String(part.type ?? "");
  return type.startsWith("tool-") ? type.slice(5) : type;
}

function MessageParts({ parts }: { parts: UIMessage["parts"] }) {
  return (
    <>
      {parts.map((rawPart, i) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const part = rawPart as any;

        if (part.type === "text") {
          if (!part.text) return null;
          return <MessageResponse key={i}>{part.text}</MessageResponse>;
        }

        if (part.type === "reasoning") {
          const isStreaming = part.state === "streaming";
          return (
            <Reasoning key={i} isStreaming={isStreaming}>
              <ReasoningTrigger />
              <ReasoningContent>{part.text ?? ""}</ReasoningContent>
            </Reasoning>
          );
        }

        const isToolPart =
          part.type === "dynamic-tool" ||
          (typeof part.type === "string" && part.type.startsWith("tool-"));

        if (isToolPart) {
          const toolName = getToolName(part);
          const isPanel = PANEL_TOOLS.has(toolName);

          return (
            <Tool key={i}>
              {part.type === "dynamic-tool" ? (
                <ToolHeader
                  type="dynamic-tool"
                  state={part.state}
                  toolName={part.toolName}
                />
              ) : (
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                <ToolHeader type={part.type as any} state={part.state} />
              )}
              <ToolContent>
                {part.input != null && <ToolInput input={part.input} />}
                {!isPanel && (
                  <ToolOutput
                    output={part.output}
                    errorText={part.errorText}
                  />
                )}
              </ToolContent>
            </Tool>
          );
        }

        return null;
      })}
    </>
  );
}

function SandboxStatusBar({ onReinitiate }: { onReinitiate: () => void }) {
  const { sandboxId, status } = useSandboxStore();
  const [working, setWorking] = useState(false);

  const handleReinstate = async () => {
    setWorking(true);
    try {
      await fetch("/api/sandbox", { method: "DELETE" });
    } finally {
      onReinitiate();
      setWorking(false);
    }
  };

  const isOffline = status === "offline";

  const dot = isOffline
    ? "bg-red-500"
    : status === "active"
      ? "bg-green-500"
      : "bg-muted-foreground/40";

  return (
    <div
      className={`flex items-center gap-2 border-b px-4 py-1.5 text-xs ${isOffline ? "bg-destructive/5 text-destructive" : "text-muted-foreground"}`}
    >
      <span className={`size-1.5 shrink-0 rounded-full ${dot}`} />
      {isOffline ? (
        <span className="font-medium">Sandbox timed out</span>
      ) : sandboxId ? (
        <span className="font-mono">{sandboxId.slice(0, 8)}…</span>
      ) : (
        <span>No sandbox</span>
      )}
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={handleReinstate}
          disabled={working}
          title={isOffline ? "Reinitiate sandbox" : "Delete sandbox and start fresh"}
          className={`flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors disabled:opacity-50 ${
            isOffline
              ? "font-medium text-destructive hover:bg-destructive/10"
              : "hover:bg-muted hover:text-foreground"
          }`}
        >
          {working ? (
            <RefreshCwIcon className="size-3 animate-spin" />
          ) : isOffline ? (
            <RefreshCwIcon className="size-3" />
          ) : (
            <Trash2Icon className="size-3" />
          )}
          {working ? "Working…" : isOffline ? "Reinitiate sandbox" : "Reset sandbox"}
        </button>
      </div>
    </div>
  );
}

export function DashboardChat() {
  const { setSnapshot } = useModel();
  const { setSandbox, setStatus, clear } = useSandboxStore();

  // Always read from the store at call time — never from a stale closure.
  const customFetch: typeof fetch = useCallback(
    async (input, init) => {
      const { sandboxId, snapshotId } = useSandboxStore.getState();

      let nextInit = init;
      if (init?.body && typeof init.body === "string") {
        try {
          const parsed = JSON.parse(init.body);
          nextInit = {
            ...init,
            body: JSON.stringify({ ...parsed, sandboxId, snapshotId }),
          };
        } catch {
          // leave body as-is if unparseable
        }
      }

      const response = await fetch(input, nextInit);

      // Both IDs in the response headers confirm the sandbox is live.
      const newSandboxId = response.headers.get("x-sandbox-id");
      const newSnapshotId = response.headers.get("x-snapshot-id");
      if (newSandboxId) setSandbox(newSandboxId, newSnapshotId ?? null);

      return response;
    },
    [setSandbox]
  );

  const transport = useMemo(
    () => new DefaultChatTransport({ api: "/api/chat", fetch: customFetch }),
    [customFetch]
  );

  const { messages, status, stop, sendMessage } = useChat({
    transport,
    onError: (error) => {
      if (error.message?.includes("410") || error.message?.includes("gone")) {
        setStatus("offline");
      }
    },
    // No onFinish — "active" is set by the x-sandbox-id header above.
    // Setting it here would race against the sandboxGone detection in the useEffect
    // and permanently override "offline" back to "active" after the stream ends.
  });

  // Preserve conversation history on reinitiate so the agent can pick up exactly
  // where it left off in the fresh environment.
  const handleReinitiate = useCallback(() => {
    clear();
  }, [clear]);

  // Extract the latest model snapshot and detect sandbox-gone signals from tool output.
  useEffect(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role !== "assistant") continue;
      for (let j = msg.parts.length - 1; j >= 0; j--) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const part = msg.parts[j] as any;
        if (part.state !== "output-available" || part.output == null) continue;

        // Detect sandbox gone signal from any tool
        if (part.output.sandboxGone === true) {
          setStatus("offline");
          return;
        }

        const name = getToolName(part);
        if (PANEL_TOOLS.has(name)) {
          setSnapshot(part.output as ModelSnapshot);
          return;
        }
      }
    }
  }, [messages, setSnapshot, setStatus]);

  return (
    <div className="flex h-full w-full flex-col">
      <SandboxStatusBar onReinitiate={handleReinitiate} />

      <Conversation className="flex-1">
        <ConversationContent className="mx-auto w-full max-w-3xl">
          {messages.length === 0 ? (
            <ConversationEmptyState
              description="Tell me what you want to model and we'll build it together."
              icon={<SparklesIcon className="size-6" />}
              title="Build a financial model"
            />
          ) : (
            messages.map((msg: UIMessage) => (
              <Message from={msg.role} key={msg.id}>
                <MessageContent>
                  <MessageParts parts={msg.parts} />
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
          <PromptInputTextarea placeholder="Describe your model..." />
          <PromptInputFooter>
            <PromptInputTools />
            <PromptInputSubmit onStop={stop} status={status} />
          </PromptInputFooter>
        </PromptInput>
      </div>
    </div>
  );
}
