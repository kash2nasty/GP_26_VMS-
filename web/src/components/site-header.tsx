import Link from "next/link"
import { ChevronLeftIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

/**
 * Header from the dashboard-01 block, with the hardcoded "Documents" title
 * replaced by a per-page title and an optional back link.
 */
export function SiteHeader({
  title,
  backHref,
  backLabel = "Back",
}: {
  title: string
  backHref?: string
  backLabel?: string
}) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mx-2 h-4 data-vertical:self-auto"
        />
        {/* Base UI composition: `render`, not `asChild`. */}
        {backHref ? (
          <Button
            render={<Link href={backHref} />}
            variant="ghost"
            size="sm"
            className="-ml-2 h-8 gap-1"
          >
            <ChevronLeftIcon className="size-4" />
            {backLabel}
          </Button>
        ) : null}
        <h1 className="truncate text-base font-medium">{title}</h1>
      </div>
    </header>
  )
}
