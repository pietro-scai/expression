"use client";

import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { DashboardChat } from "./chat";
import { ModelProvider } from "./model-context";
import { ModelPanel } from "./model-panel";
import { useConversationStore } from "@/lib/conversation-store";

function DashboardLayoutInner() {
  const searchParams = useSearchParams();
  const activeId = searchParams.get("c");

  // Fine-grained selectors so modelSnapshot changes don't re-render the layout.
  const streamingIds = useConversationStore((s) => s.streamingIds);
  const newConvVersion = useConversationStore((s) => s.newConvVersion);
  const nullSlotConversationId = useConversationStore((s) => s.nullSlotConversationId);

  // The null-slot is visible when there's no activeId, OR when the activeId is the
  // conversation that the null-slot is currently handling (assigned mid-stream).
  // This prevents history.replaceState from switching to a blank per-id slot.
  const showNullSlot = !activeId || activeId === nullSlotConversationId;

  // Conversations to keep mounted: streaming ones + the currently active one.
  // Exclude the nullSlotConversationId — the null-slot IS that slot, no per-id needed.
  const mountedIds = useMemo(() => {
    const ids = new Set(streamingIds);
    if (activeId) ids.add(activeId);
    if (nullSlotConversationId) ids.delete(nullSlotConversationId);
    return [...ids];
  }, [streamingIds, activeId, nullSlotConversationId]);

  return (
    <ModelProvider activeConversationId={activeId}>
      <ResizablePanelGroup
        orientation="horizontal"
        className="flex-1 overflow-hidden"
      >
        <ResizablePanel defaultSize={50} minSize={30}>
          {/* New-conversation slot — visible when no activeId, or when the null-slot
              has claimed the current activeId (prevents blank flash mid-stream).
              Keyed on newConvVersion so "New conversation" gives a fresh instance. */}
          <div className={showNullSlot ? "h-full" : "hidden"}>
            <DashboardChat
              key={`new-${newConvVersion}`}
              conversationId={null}
              isActive={showNullSlot}
            />
          </div>

          {/* Per-conversation slots — mounted once, shown/hidden as needed. */}
          {mountedIds.map((id) => (
            <div key={id} className={id === activeId ? "h-full" : "hidden"}>
              <DashboardChat
                conversationId={id}
                isActive={id === activeId}
              />
            </div>
          ))}
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel defaultSize={50} minSize={20}>
          <ModelPanel />
        </ResizablePanel>
      </ResizablePanelGroup>
    </ModelProvider>
  );
}

export function DashboardLayout() {
  return (
    <Suspense>
      <DashboardLayoutInner />
    </Suspense>
  );
}
