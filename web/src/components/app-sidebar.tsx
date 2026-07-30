"use client"

/**
 * Sidebar, reduced from the dashboard-01 demo version.
 *
 * The block shipped five placeholder nav sections, a documents list and a user
 * account menu. All of it is gone: there is no authentication in this phase, so a
 * user avatar would be decoration implying a login that does not exist, and dead
 * nav links teach the reader that things are clickable when they are not. What is
 * left is the routes that actually resolve.
 *
 * The brand mark carries the one gradient in the application. It is on a 28px
 * square rather than on a card or a header, so it can be saturated enough to read
 * as a mark without any text ever sitting on top of it.
 */

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { EyeIcon, ListIcon, VideoIcon } from "lucide-react"

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
  {
    title: "Sessions",
    url: "/sessions",
    icon: ListIcon,
    hint: "Everything recorded so far",
  },
  {
    title: "New session",
    url: "/capture",
    icon: VideoIcon,
    hint: "Record from this browser",
  },
]

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
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
              className="h-auto gap-2.5 data-[slot=sidebar-menu-button]:!p-2"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-linear-to-br from-primary to-chart-3 text-primary-foreground shadow-sm">
                <EyeIcon className="!size-4" />
              </span>
              <span className="grid gap-0.5 leading-none">
                <span className="font-heading text-[0.95rem] font-semibold">
                  Oculomotor Screening
                </span>
                <span className="text-[0.7rem] text-muted-foreground">
                  head, eye, eyelid and face
                </span>
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent className="flex flex-col gap-1">
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    render={<Link href={item.url} />}
                    tooltip={item.hint}
                    isActive={pathname.startsWith(item.url)}
                    className="h-auto py-2"
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
        <p className="inset-panel px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">
          Screening data only. Not a diagnosis of any condition, and not a
          clinical determination.
        </p>
      </SidebarFooter>
    </Sidebar>
  )
}
