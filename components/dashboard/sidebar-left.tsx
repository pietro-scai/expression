"use client"

import * as React from "react"
import { UserButton } from "@clerk/nextjs"

import { Logo } from "@/components/logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"

export function SidebarLeft({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" className="border-r-0" {...props}>
      <SidebarHeader className="overflow-hidden items-center group-data-[collapsible=icon]:h-24">
        <div className="transition-transform duration-200 origin-center group-data-[collapsible=icon]:rotate-90">
          <Logo />
        </div>
      </SidebarHeader>
      <SidebarContent />
      <SidebarFooter className="flex items-center justify-center p-3">
        <UserButton />
      </SidebarFooter>
    </Sidebar>
  )
}
