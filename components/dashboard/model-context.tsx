"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { ModelSnapshot } from "@/lib/model-types";

type ModelContextType = {
  snapshots: Record<string, ModelSnapshot>;
  activeModel: string | null;
  setSnapshot: (snapshot: ModelSnapshot) => void;
  setActiveModel: (name: string) => void;
};

export const ModelContext = createContext<ModelContextType>({
  snapshots: {},
  activeModel: null,
  setSnapshot: () => {},
  setActiveModel: () => {},
});

export function ModelProvider({ children }: { children: React.ReactNode }) {
  const [snapshots, setSnapshots] = useState<Record<string, ModelSnapshot>>({});
  const [activeModel, setActiveModel] = useState<string | null>(null);

  const setSnapshot = useCallback((snapshot: ModelSnapshot) => {
    const key = snapshot.definition?.name ?? "Model";
    setSnapshots((prev) => ({ ...prev, [key]: snapshot }));
    setActiveModel(key);
  }, []);

  return (
    <ModelContext.Provider value={{ snapshots, activeModel, setSnapshot, setActiveModel }}>
      {children}
    </ModelContext.Provider>
  );
}

export function useModel() {
  return useContext(ModelContext);
}
