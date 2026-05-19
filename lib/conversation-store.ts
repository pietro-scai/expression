"use client";

import { create } from "zustand";
import type { ModelSnapshot } from "./model-types";

interface ConversationState {
  // Conversations with active in-flight streams — keep these mounted.
  streamingIds: Set<string>;
  mountStreaming: (id: string) => void;
  unmountStreaming: (id: string) => void;

  // Per-conversation model snapshots (drives the right-hand model panel).
  // Key "__new__" is used for the null-id / new-conversation slot.
  modelSnapshots: Record<string, ModelSnapshot[]>;
  setModelSnapshots: (id: string | null, snapshots: ModelSnapshot[]) => void;
  setModelSnapshot: (id: string | null, snapshot: ModelSnapshot) => void;

  // Increment this to reset (remount) the new-conversation slot.
  newConvVersion: number;
  bumpNewConversation: () => void;

  // The conversationId the null-slot is currently handling (assigned mid-stream).
  // The layout uses this to keep the null-slot visible even after history.replaceState
  // updates useSearchParams — preventing a blank flash to a fresh per-id slot.
  nullSlotConversationId: string | null;
  setNullSlotConversationId: (id: string | null) => void;
}

export const useConversationStore = create<ConversationState>((set) => ({
  streamingIds: new Set(),

  mountStreaming: (id) =>
    set((s) => {
      if (s.streamingIds.has(id)) return s; // no-op
      return { streamingIds: new Set([...s.streamingIds, id]) };
    }),

  unmountStreaming: (id) =>
    set((s) => {
      if (!s.streamingIds.has(id)) return s; // no-op
      const next = new Set(s.streamingIds);
      next.delete(id);
      return { streamingIds: next };
    }),

  modelSnapshots: {},

  setModelSnapshots: (id, snapshots) =>
    set((s) => {
      const key = id ?? "__new__";
      if (s.modelSnapshots[key] === snapshots) return s; // same reference, no-op
      return { modelSnapshots: { ...s.modelSnapshots, [key]: snapshots } };
    }),

  setModelSnapshot: (id, snapshot) =>
    set((s) => {
      const key = id ?? "__new__";
      const prev = s.modelSnapshots[key];
      if (prev?.length === 1 && prev[0] === snapshot) return s; // no-op
      return { modelSnapshots: { ...s.modelSnapshots, [key]: [snapshot] } };
    }),

  newConvVersion: 0,
  bumpNewConversation: () =>
    set((s) => ({
      newConvVersion: s.newConvVersion + 1,
      nullSlotConversationId: null,
    })),

  nullSlotConversationId: null,
  setNullSlotConversationId: (id) => set({ nullSlotConversationId: id }),
}));
