"use client";
import { ChatIcon, Info } from "@phosphor-icons/react"
import * as React from "react";
import { Suspense } from "react";
import { UserButton } from "@clerk/nextjs";
import { useRouter, useSearchParams } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { PlusIcon, Trash2Icon } from "lucide-react";

import { Logo } from "@/components/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useConversations, useDeleteConversation } from "@/lib/queries";
import { useConversationStore } from "@/lib/conversation-store";
import { useQueryClient } from "@tanstack/react-query";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";


function SidebarNav() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeConvId = searchParams.get("c");

  const { data: convs } = useConversations();
  const { mutate: deleteConv } = useDeleteConversation();
  const qc = useQueryClient();
  const { bumpNewConversation } = useConversationStore();

  const prefetchConversation = (id: string) =>
    qc.prefetchQuery({
      queryKey: ["conversations", id],
      queryFn: () => fetch(`/api/conversations/${id}`).then((r) => r.json()),
      staleTime: 60_000,
    });

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteConv(id, {
      onSuccess: () => {
        if (activeConvId === id) router.push("/expr");
      },
    });
  };

  return (
    <SidebarContent>
      {/* New conversation */}
      <SidebarGroup>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => { bumpNewConversation(); router.push("/expr"); }}
              className="gap-2"
            >
              <PlusIcon className="size-4" />
              <span>New conversation</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>

      {/* Conversation history */}
      {convs && convs.length > 0 && (
        <SidebarGroup>
          <SidebarGroupLabel>Conversations</SidebarGroupLabel>
          <SidebarMenu>
            {convs.map((conv) => (
              <SidebarMenuItem key={conv.id}>
                <SidebarMenuButton
                  isActive={conv.id === activeConvId}
                  onClick={() => router.push(`/expr?c=${conv.id}`)}
                  onMouseEnter={() => prefetchConversation(conv.id)}
                  className="flex flex-row items-start gap-0.5 h-auto py-2"
                >
                  <ChatIcon />
                  <span className="truncate w-full text-sm leading-tight">
                    {conv.title ?? "Untitled"}
                  </span>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info />
                    </TooltipTrigger>
                    <TooltipContent>
                      <span className="text-xs text-muted-foreground">
                        {formatDistanceToNow(new Date(conv.updatedAt), {
                          addSuffix: true,
                        })}
                        {conv.modelName && (
                          <>
                            {" · "}
                            <span className="font-mono">{conv.modelName}</span>
                          </>
                        )}
                      </span>
                    </TooltipContent>
                  </Tooltip>
                </SidebarMenuButton>
                <SidebarMenuAction
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="text-muted-foreground hover:text-destructive"
                  title="Delete conversation"
                >
                  <Trash2Icon className="size-3.5" />
                </SidebarMenuAction>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      )}
    </SidebarContent>
  );
}

export function SidebarLeft({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";

  return (
    <Sidebar collapsible="icon" className="border-r-0" {...props}>
      <SidebarHeader className="overflow-hidden items-center pt-4!">
        <Logo shortText="x" collapsed={collapsed} />
      </SidebarHeader>
      <Suspense fallback={<SidebarContent />}>
        <SidebarNav />
      </Suspense>
      <SidebarFooter className="flex items-center justify-center p-3">
        <UserButton />
      </SidebarFooter>
    </Sidebar>
  );
}
