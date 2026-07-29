/**
 * The dashboard-01 layout shell.
 *
 * Horizontal padding, max width and vertical rhythm live here rather than being
 * repeated as `px-4 lg:px-6` on every block inside every page. That repetition was
 * the main reason the pages read as machine-assembled: each section carried its
 * own margins, so nothing shared a spacing scale and wide screens stretched the
 * content into a single flat column.
 */

import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import { DisclaimerFooter } from "@/components/disclaimer"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

export function DashboardShell({
  title,
  backHref,
  backLabel,
  children,
}: {
  title: string
  backHref?: string
  backLabel?: string
  children: React.ReactNode
}) {
  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 68)",
          "--header-height": "calc(var(--spacing) * 13)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader title={title} backHref={backHref} backLabel={backLabel} />
        <div className="@container/main flex flex-1 flex-col">
          <div className="mx-auto w-full max-w-[1360px] flex-1 space-y-10 px-5 py-8 lg:px-8 lg:py-10">
            {children}
          </div>
          <DisclaimerFooter />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

/**
 * Section heading with optional description and right-aligned actions.
 *
 * Gives every page the same label/description/action rhythm instead of each one
 * inventing its own arrangement of an h2 and a button.
 */
export function SectionHeader({
  title,
  description,
  actions,
  as: Heading = "h2",
}: {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  as?: "h1" | "h2"
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="space-y-1">
        <Heading className="text-xl font-semibold tracking-tight">{title}</Heading>
        {description ? (
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 gap-2">{actions}</div> : null}
    </div>
  )
}

/** A titled block of content with consistent spacing between heading and body. */
export function Section({
  title,
  description,
  actions,
  children,
}: {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="space-y-4">
      <SectionHeader title={title} description={description} actions={actions} />
      {children}
    </section>
  )
}
