"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { ModelSnapshot } from "@/lib/model-types";

type ModelContextType = {
  snapshots: ModelSnapshot[];
  setSnapshot: (snapshot: ModelSnapshot) => void;
  setAllSnapshots: (snapshots: ModelSnapshot[]) => void;
};

export const ModelContext = createContext<ModelContextType>({
  snapshots: [],
  setSnapshot: () => {},
  setAllSnapshots: () => {},
});

export function ModelProvider({ children }: { children: React.ReactNode }) {
  const [snapshots, setSnapshots] = useState<ModelSnapshot[]>([]);

  const setSnapshot = useCallback((snapshot: ModelSnapshot) => {
    setSnapshots([snapshot]);
  }, []);

  const setAllSnapshots = useCallback((incoming: ModelSnapshot[]) => {
    if (incoming.length === 0) return;
    setSnapshots(incoming);
  }, []);

  return (
    <ModelContext.Provider value={{ snapshots, setSnapshot, setAllSnapshots }}>
      {children}
    </ModelContext.Provider>
  );
}

export function useModel() {
  return useContext(ModelContext);
}
