import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SandboxStatus = "unknown" | "active" | "offline";

interface SandboxStore {
  sandboxId: string | null;
  snapshotId: string | null;
  status: SandboxStatus;
  setSandbox: (sandboxId: string, snapshotId: string | null) => void;
  setStatus: (status: SandboxStatus) => void;
  clear: () => void;
}

export const useSandboxStore = create<SandboxStore>()(
  persist(
    (set) => ({
      sandboxId: null,
      snapshotId: null,
      status: "unknown" as SandboxStatus,
      setSandbox: (sandboxId, snapshotId) =>
        set({ sandboxId, snapshotId, status: "active" }),
      setStatus: (status) => set({ status }),
      clear: () => set({ sandboxId: null, status: "unknown" }),
    }),
    {
      name: "sweet-sandbox",
      partialize: (state) => ({
        sandboxId: state.sandboxId,
        snapshotId: state.snapshotId,
      }),
    }
  )
);
