"use client";

import { createContext, useContext } from "react";
import type { ModelSnapshot } from "@/lib/model-types";
import { useConversationStore } from "@/lib/conversation-store";

type ModelContextType = {
  snapshots: ModelSnapshot[];
};

export const ModelContext = createContext<ModelContextType>({ snapshots: [] });

// Stable fallback so the Zustand selector never returns a new [] reference,
// which would cause useSyncExternalStore to loop.
const EMPTY: ModelSnapshot[] = [];

export function ModelProvider({
  activeConversationId,
  children,
}: {
  activeConversationId: string | null;
  children: React.ReactNode;
}) {
  const snapshots = useConversationStore(
    (s) => s.modelSnapshots[activeConversationId ?? "__new__"] ?? EMPTY
  );

  return (
    <ModelContext.Provider value={{ snapshots }}>
      {children}
    </ModelContext.Provider>
  );
}

export function useModel() {
  return useContext(ModelContext);
}
