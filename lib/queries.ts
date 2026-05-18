"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type ConversationListItem = {
  id: string;
  title: string | null;
  modelName: string | null;
  updatedAt: string;
};

export type ModelListItem = {
  id: string;
  name: string;
  version: number;
  updatedAt: string;
};

export type ConversationDetail = {
  id: string;
  title: string | null;
  modelId: string | null;
  messages: { id: string; role: string; parts: unknown[] }[];
  model: { source: string; modelJson: unknown; resultJson: unknown } | null;
};

export function useConversations() {
  return useQuery<ConversationListItem[]>({
    queryKey: ["conversations"],
    queryFn: () => fetch("/api/conversations").then((r) => r.json()),
  });
}

export function useConversation(id: string | null) {
  return useQuery<ConversationDetail>({
    queryKey: ["conversations", id],
    queryFn: () => fetch(`/api/conversations/${id}`).then((r) => r.json()),
    enabled: !!id,
    refetchOnMount: "always", // always fetch fresh when switching conversations
  });
}

export function useModels() {
  return useQuery<ModelListItem[]>({
    queryKey: ["models"],
    queryFn: () => fetch("/api/models").then((r) => r.json()),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      fetch(`/api/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}

export function useInvalidateAfterSave() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["conversations"] });
    qc.invalidateQueries({ queryKey: ["models"] });
  };
}
