import Link from "next/link"
import { SearchXIcon } from "lucide-react"

import { DashboardShell } from "@/components/dashboard-shell"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

export default function SessionNotFound() {
  return (
    <DashboardShell
      title="Session not found"
      backHref="/sessions"
      backLabel="Sessions"
    >
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center gap-4 py-14 text-center">
          <span className="flex size-12 items-center justify-center rounded-full bg-muted">
            <SearchXIcon className="size-5 text-muted-foreground" />
          </span>
          <div className="space-y-1.5">
            <p className="font-heading text-lg font-semibold">No such session</p>
            <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
              Nothing in the{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                sessions/
              </code>{" "}
              directory matches that identifier. It may have been deleted, in which
              case the files are in{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                sessions/_deleted/
              </code>
              .
            </p>
          </div>
          <Button render={<Link href="/sessions" />} size="sm">
            Back to all sessions
          </Button>
        </CardContent>
      </Card>
    </DashboardShell>
  )
}
