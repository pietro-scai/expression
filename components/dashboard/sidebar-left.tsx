"use client"

import * as React from "react"

import { Logo } from "@/components/logo"
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
} from "@/components/ui/sidebar"

export function SidebarLeft({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar className="border-r-0" {...props}>
      <SidebarHeader className="items-start">
        <Logo />
      </SidebarHeader>
      <SidebarContent></SidebarContent>
    </Sidebar>
  )
}
