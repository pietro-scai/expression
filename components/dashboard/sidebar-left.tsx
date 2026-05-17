"use client"

import * as React from "react"
import { UserButton } from "@clerk/nextjs"

import { Logo } from "@/components/logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  useSidebar,
} from "@/components/ui/sidebar"

export function SidebarLeft({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  const { state } = useSidebar()
  const collapsed = state === "collapsed"

  return (
    <Sidebar collapsible="icon" className="border-r-0" {...props}>
      <SidebarHeader className="overflow-hidden items-center pt-4!">
        <Logo shortText="x" collapsed={collapsed} />
      </SidebarHeader>
      <SidebarContent />
      <SidebarFooter className="flex items-center justify-center p-3">
        <UserButton />
      </SidebarFooter>
    </Sidebar>
  )
}
