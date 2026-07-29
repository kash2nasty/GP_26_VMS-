"use client"

/**
 * Sidebar, reduced from the dashboard-01 demo version.
 *
 * The block shipped five placeholder nav sections, a documents list, and a user
 * account menu. All of it is removed: there is no authentication in this phase,
 * so a user avatar would be decoration implying a login that does not exist, and
 * dead nav links teach the reader that things are clickable when they are not.
 * What is left is the routes that actually resolve.
 */

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { ActivityIcon, ListIcon, VideoIcon } from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const navItems = [
  { title: "Sessions", url: "/sessions", icon: ListIcon },
  { title: "New session", url: "/capture", icon: VideoIcon },
]

export function AppSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            {/* This shadcn build is on Base UI, not Radix: composition uses the
                `render` prop rather than `asChild`. */}
            <SidebarMenuButton
              render={<Link href="/sessions" />}
              className="data-[slot=sidebar-menu-button]:!p-1.5"
            >
              <ActivityIcon className="!size-5" />
              <span className="text-base font-semibold">VMS Screening</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent className="flex flex-col gap-2">
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    render={<Link href={item.url} />}
                    tooltip={item.title}
                    isActive={pathname.startsWith(item.url)}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <p className="px-2 py-1 text-xs leading-relaxed text-muted-foreground">
          Screening data only. Not a clinical determination.
        </p>
      </SidebarFooter>
    </Sidebar>
  )
}
