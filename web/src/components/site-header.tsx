import Link from "next/link"
import { ChevronLeftIcon } from "lucide-react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

/**
 * Sticky top bar.
 *
 * The title here is the small, always-visible one. Each page also renders its own
 * h1 in the content, and that duplication is deliberate rather than an oversight:
 * this bar stays put while the page scrolls, so on a long session detail page it is
 * the only thing still saying which session is being read.
 *
 * Sticky is new. The detail page runs several screens, and losing the back link as
 * soon as you scrolled meant the only route back was the browser button.
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
    <header className="sticky top-0 z-30 flex h-(--header-height) shrink-0 items-center gap-2 border-b bg-background/85 backdrop-blur-md">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mx-1.5 h-4 data-vertical:self-auto"
        />
        {/* Base UI composition: `render`, not `asChild`. */}
        {backHref ? (
          <Button
            render={<Link href={backHref} />}
            variant="ghost"
            size="sm"
            className="-ml-1 gap-1"
          >
            <ChevronLeftIcon className="size-4" />
            {backLabel}
          </Button>
        ) : null}
        <h1 className="truncate text-sm font-medium">{title}</h1>
        <ThemeToggle className="ml-auto" />
      </div>
    </header>
  )
}
