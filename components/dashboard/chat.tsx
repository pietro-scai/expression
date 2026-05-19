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
import type { ChartSpec } from "@/lib/chart-types";
import { ChartRenderer } from "./chart-renderer";
import { useSandboxStore } from "@/lib/sandbox-store";
import { DEFAULT_THINKING_WORDS, useLogoStore } from "@/lib/logo-store";
import { useConversationStore } from "@/lib/conversation-store";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import type { UIMessage } from "ai";
import { RefreshCwIcon, SparklesIcon, Trash2Icon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import type { ConversationDetail } from "@/lib/queries";

// Tool names whose output is displayed in the right panel — show compact summary, not raw JSON.
const PANEL_TOOLS = new Set(["update_model", "run_model"]);

// Tool names that render custom UI instead of raw JSON output.
const CHART_TOOL = "render_chart";

function getToolName(part: Record<string, unknown>): string {
  if (part.type === "dynamic-tool") return String(part.toolName ?? "");
  const type = String(part.type ?? "");
  return type.startsWith("tool-") ? type.slice(5) : type;
}

function PanelToolSummary({ output }: { output: unknown }) {
  if (!Array.isArray(output) || output.length === 0) return null;
  const snapshots = output as ModelSnapshot[];
  const errorSnap = snapshots.find((s) => s.execution?.status === "error");
  const cmdLog = snapshots[0]?.cmdLog;
  return (
    <div className="space-y-2 text-xs">
      {errorSnap ? (
        <div className="rounded bg-destructive/10 p-2 font-mono text-destructive whitespace-pre-wrap">
          {errorSnap.execution?.message}
        </div>
      ) : (
        <div className="text-muted-foreground">
          {snapshots.length} model{snapshots.length !== 1 ? "s" : ""} updated — results sent to panel
        </div>
      )}
      {cmdLog && (
        <details>
          <summary className="cursor-pointer select-none text-muted-foreground hover:text-foreground">
            Command output
          </summary>
          <pre className="mt-1 overflow-x-auto rounded bg-muted/50 p-2 text-xs">{cmdLog}</pre>
        </details>
      )}
    </div>
  );
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
          const isChart = toolName === CHART_TOOL;

          if (isChart && part.state === "output-available" && part.output) {
            return (
              <ChartRenderer key={i} spec={part.output as ChartSpec} />
            );
          }

          if (isChart) {
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
              </Tool>
            );
          }

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
                {isPanel ? (
                  part.state === "output-available" && part.output != null && (
                    <PanelToolSummary output={part.output} />
                  )
                ) : (
                  <ToolOutput output={part.output} errorText={part.errorText} />
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
        <span className="font-mono">{sandboxId}</span>
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

interface DashboardChatProps {
  conversationId: string | null;
  isActive: boolean;
}

function DashboardChatInner({ conversationId: propConversationId, isActive }: DashboardChatProps) {
  const { setSandbox, setStatus, clear } = useSandboxStore();
  const { startThinking, stopThinking } = useLogoStore();
  // Fine-grained selectors — only subscribe to the functions we use.
  // Store functions are stable references, so this only re-renders when
  // streamingIds/modelSnapshots change in ways relevant to this component.
  const mountStreaming = useConversationStore((s) => s.mountStreaming);
  const unmountStreaming = useConversationStore((s) => s.unmountStreaming);
  const setModelSnapshots = useConversationStore((s) => s.setModelSnapshots);
  const setModelSnapshot = useConversationStore((s) => s.setModelSnapshot);
  const qc = useQueryClient();

  // conversationId tracked as ref (for stable closure in customFetch) + state.
  // Starts from the prop but can diverge when the server assigns an ID to a
  // brand-new conversation.
  const conversationIdRef = useRef<string | null>(propConversationId);
  const [conversationId, setConversationId] = useState<string | null>(propConversationId);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // Always read from the store at call time — never from a stale closure.
  const customFetch: typeof fetch = useCallback(
    async (input, init) => {
      const { sandboxId, snapshotId } = useSandboxStore.getState();
      const convId = conversationIdRef.current;

      let nextInit = init;
      if (init?.body && typeof init.body === "string") {
        try {
          const parsed = JSON.parse(init.body);
          nextInit = {
            ...init,
            body: JSON.stringify({ ...parsed, sandboxId, snapshotId, conversationId: convId }),
          };
        } catch {
          // leave body as-is if unparseable
        }
      }

      const response = await fetch(input, nextInit);

      const newSandboxId = response.headers.get("x-sandbox-id");
      const newSnapshotId = response.headers.get("x-snapshot-id");
      if (newSandboxId) setSandbox(newSandboxId, newSnapshotId ?? null);

      // Update URL when the server assigns an ID to a new conversation.
      // history.replaceState DOES trigger useSearchParams in Next.js App Router,
      // so we register nullSlotConversationId first to keep the layout on this slot.
      const newConvId = response.headers.get("x-conversation-id");
      if (newConvId && newConvId !== conversationIdRef.current) {
        conversationIdRef.current = newConvId;
        setConversationId(newConvId);
        // Register before replaceState so the layout sees nullSlotConversationId===activeId
        // in the same render batch and doesn't switch to a blank per-id slot.
        if (propConversationId === null) {
          useConversationStore.getState().setNullSlotConversationId(newConvId);
        }
        window.history.replaceState(null, "", `?c=${newConvId}`);
        qc.invalidateQueries({ queryKey: ["conversations"] });
      }

      return response;
    },
    [setSandbox, qc, propConversationId]
  );

  const transport = useMemo(
    () => new DefaultChatTransport({ api: "/api/chat", fetch: customFetch }),
    [customFetch]
  );

  const onFinish = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["conversations"] });
    qc.invalidateQueries({ queryKey: ["models"] });
  }, [qc]);

  const { messages, status, stop, sendMessage, setMessages } = useChat({
    transport,
    onError: (error) => {
      if (error.message?.includes("410") || error.message?.includes("gone")) {
        setStatus("offline");
      }
    },
    onFinish,
  });

  // Tracks the current in-memory message count on every render so the restore
  // effect can compare without a stale closure.
  const messagesLengthRef = useRef(messages.length);
  messagesLengthRef.current = messages.length;

  // -------------------------------------------------------------------
  // Streaming store lifecycle: keep this slot mounted while streaming.
  // -------------------------------------------------------------------
  useEffect(() => {
    if (!conversationId) return;
    if (status === "submitted" || status === "streaming") {
      mountStreaming(conversationId);
    } else {
      // Small delay so model state is written before the slot could unmount.
      const t = setTimeout(() => unmountStreaming(conversationId), 500);
      return () => clearTimeout(t);
    }
  }, [conversationId, status, mountStreaming, unmountStreaming]);

  // -------------------------------------------------------------------
  // Polling: if we loaded a conversation whose last message is "user"
  // (stream was in-flight when we fetched), refetch every 2 s until the
  // assistant response arrives server-side.
  // -------------------------------------------------------------------
  const [pollInterval, setPollInterval] = useState<number | false>(false);

  const { data: convData } = useQuery<ConversationDetail>({
    queryKey: ["conversations", conversationId],
    queryFn: () =>
      fetch(`/api/conversations/${conversationId}`).then((r) => r.json()),
    enabled: !!conversationId,
    refetchOnMount: "always",
    refetchInterval: pollInterval,
  });

  useEffect(() => {
    if (!convData) return;
    const lastDb = convData.messages[convData.messages.length - 1];
    const lastInMemory = messages[messages.length - 1];
    // Only poll when DB shows a pending user message AND in-memory doesn't already
    // have the assistant response (prevents false "generating" flash after stream).
    const pending =
      lastDb?.role === "user" &&
      status !== "streaming" &&
      status !== "submitted" &&
      lastInMemory?.role !== "assistant";
    setPollInterval(pending ? 2000 : false);
  }, [convData, messages, status]);

  // -------------------------------------------------------------------
  // Restore messages + model when conversation data arrives.
  // -------------------------------------------------------------------
  useEffect(() => {
    if (!conversationId) {
      setModelSnapshots(null, []);
      return;
    }
    if (!convData) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const uiMessages: UIMessage[] = (convData.messages ?? []).map((m: any) => ({
      id: m.id,
      role: m.role,
      parts: m.parts,
    }));

    // Only restore messages from DB when we're not actively streaming,
    // and only if the DB has MORE messages than we have in memory.
    // Using strict > (not >=) means we never overwrite a just-finished stream
    // with its DB copy — in-memory is already correct and the DB write may have
    // raced (concurrent after() calls can insert assistant before user, flipping order).
    if (status !== "streaming" && status !== "submitted") {
      if (uiMessages.length > messagesLengthRef.current) {
        setMessages(uiMessages);
      }
    }

    if (convData.model?.source) {
      setModelSnapshots(conversationId, [
        {
          source: convData.model.source,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          definition: (convData.model.modelJson as any) ?? undefined,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          execution: (convData.model.resultJson as any) ?? undefined,
        },
      ]);
    } else {
      setModelSnapshots(conversationId, []);
    }
  }, [conversationId, convData, setMessages, setModelSnapshots, status]);

  // -------------------------------------------------------------------
  // Logo thinking animation — only animate for the visible conversation.
  // -------------------------------------------------------------------
  useEffect(() => {
    if (!isActive) return;
    if (status === "submitted" || status === "streaming") {
      startThinking(DEFAULT_THINKING_WORDS);
      return;
    }
    stopThinking();
  }, [isActive, startThinking, status, stopThinking]);

  // Stop thinking when this conversation is hidden mid-stream.
  useEffect(() => {
    if (!isActive) stopThinking();
  }, [isActive, stopThinking]);

  const handleReinitiate = useCallback(() => {
    clear();
  }, [clear]);

  // Extract model snapshots from tool output and write to the store.
  useEffect(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role !== "assistant") continue;
      for (let j = msg.parts.length - 1; j >= 0; j--) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const part = msg.parts[j] as any;
        if (part.state !== "output-available" || part.output == null) continue;

        if (part.output.sandboxGone === true) {
          setStatus("offline");
          return;
        }

        const name = getToolName(part);
        if (PANEL_TOOLS.has(name)) {
          const output = part.output;
          if (Array.isArray(output)) {
            setModelSnapshots(conversationId, output as ModelSnapshot[]);
          } else {
            setModelSnapshot(conversationId, output as ModelSnapshot);
          }
          return;
        }
      }
    }
  }, [messages, conversationId, setModelSnapshots, setModelSnapshot, setStatus]);

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

      {/* Generating indicator: shown when we're polling for a pending assistant response */}
      {pollInterval !== false && messages.length > 0 && (
        <div className="border-t px-4 py-2 text-xs text-muted-foreground flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />
          Generating response — will appear when ready
        </div>
      )}

      <div className="border-t p-4">
        <PromptInput
          className="mx-auto max-w-3xl"
          onSubmit={({ text }) => {
            if (!text.trim()) return;
            startThinking(DEFAULT_THINKING_WORDS);
            sendMessage({ text });
          }}
        >
          <PromptInputTextarea placeholder="Describe your model..." />
          <PromptInputFooter>
            <PromptInputTools />
            <PromptInputSubmit
              onStop={() => {
                stopThinking();
                stop();
              }}
              status={status}
            />
          </PromptInputFooter>
        </PromptInput>
      </div>
    </div>
  );
}

export function DashboardChat(props: DashboardChatProps) {
  return <DashboardChatInner {...props} />;
}
