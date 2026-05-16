"use client";

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { DashboardChat } from "./chat";
import { ModelProvider } from "./model-context";
import { ModelPanel } from "./model-panel";

export function DashboardLayout() {
  return (
    <ModelProvider>
      <ResizablePanelGroup
        orientation="horizontal"
        className="flex-1 overflow-hidden"
      >
        <ResizablePanel defaultSize={50} minSize={30}>
          <DashboardChat />
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={50} minSize={20}>
          <ModelPanel />
        </ResizablePanel>
      </ResizablePanelGroup>
    </ModelProvider>
  );
}
