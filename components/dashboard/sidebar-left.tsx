"use client"

import * as React from "react"

import {
  Sidebar,
  SidebarContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  CommandIcon,
  AudioWave01Icon,
  SearchIcon,
  SparklesIcon,
  HomeIcon,
  InboxIcon,
  CalendarIcon,
  Settings05Icon,
  CubeIcon,
  Delete02Icon,
  MessageQuestionIcon,
} from "@hugeicons/core-free-icons"

// This is sample data.
const data = {
  navMain: [
    {
      title: "Search",
      url: "#",
      icon: <HugeiconsIcon icon={SearchIcon} strokeWidth={2} />,
    },
  ],
  navChats: [
    {
      title: "Calendar",
      url: "#",
      icon: <HugeiconsIcon icon={CalendarIcon} strokeWidth={2} />,
    },
  ],
}

export function SidebarLeft({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar className="border-r-0" {...props}>
      <SidebarHeader>Sweet</SidebarHeader>
      <SidebarContent></SidebarContent>
    </Sidebar>
  )
}
