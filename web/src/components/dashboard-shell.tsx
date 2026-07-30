/**
 * The application shell.
 *
 * SPACING LIVES HERE, ON PURPOSE
 *     Horizontal padding, measure and vertical rhythm are set once here rather
 *     than repeated as `px-4 lg:px-6` on every block inside every page. That
 *     repetition was the main reason the pages read as machine-assembled: each
 *     section carried its own margins, so nothing shared a scale.
 *
 * WHAT CHANGED FROM THE FIRST VERSION
 *     1. The measure came down from 1360px to 1180px. At 1360 a metric row on a
 *        wide monitor stretched a two-word label and a five-character number to
 *        opposite ends of half a metre of screen, and the explanation beneath it
 *        ran to 160 characters a line. Nothing was wrong with any single box; the
 *        page was simply too wide to read.
 *     2. The flat `space-y-10` between every child became the `page-stack`
 *        utility, whose gap is deliberately larger than the gap inside a section.
 *        A heading now sits closer to what it labels than to the section above it,
 *        which is the whole job of vertical rhythm and was the thing most visibly
 *        missing.
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
          "--sidebar-width": "calc(var(--spacing) * 64)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader title={title} backHref={backHref} backLabel={backLabel} />
        <div className="@container/main flex flex-1 flex-col">
          <div className="page-stack mx-auto w-full max-w-[1180px] flex-1 px-5 py-7 lg:px-8 lg:py-9">
            {children}
          </div>
          <DisclaimerFooter />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

/**
 * Page or section heading, with optional description and right-aligned actions.
 *
 * Gives every page the same label, description and action rhythm instead of each
 * one inventing its own arrangement of a heading and a button.
 */
export function SectionHeader({
  title,
  description,
  actions,
  eyebrow,
  as: Heading = "h2",
}: {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  /** Small label above the heading. Orients a section without a second sentence. */
  eyebrow?: string
  as?: "h1" | "h2"
}) {
  const isPage = Heading === "h1"
  return (
    // Page headings align their action to the TOP, section headings to the
    // baseline. A page description runs two or three lines, and bottom-aligning
    // against it left the primary button floating in the middle of the block with
    // nothing on its row.
    <div
      className={`flex flex-wrap justify-between gap-x-6 gap-y-3 ${
        isPage ? "items-start" : "items-end"
      }`}
    >
      <div className="space-y-1">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <Heading
          className={
            isPage
              ? "text-[1.6rem] leading-tight font-semibold"
              : "text-lg leading-snug font-semibold"
          }
        >
          {title}
        </Heading>
        {description ? (
          // Around 62 characters a line. Wider than this and the eye loses the
          // start of the next line, which matters most for the explanatory copy
          // that carries all the caveats.
          <p className="max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      ) : null}
    </div>
  )
}

/** A titled block: heading tight against its content, generous gap outside it. */
export function Section({
  title,
  description,
  actions,
  eyebrow,
  children,
}: {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  eyebrow?: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-4">
      <SectionHeader
        title={title}
        description={description}
        actions={actions}
        eyebrow={eyebrow}
      />
      {children}
    </section>
  )
}
