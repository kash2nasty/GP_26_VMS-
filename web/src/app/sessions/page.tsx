import Link from "next/link"
import { AlertTriangleIcon, VideoIcon } from "lucide-react"

import { ApiError } from "@/components/api-error"
import { DashboardShell, Section, SectionHeader } from "@/components/dashboard-shell"
import { ScreeningDisclaimer } from "@/components/disclaimer"
import { OverviewCards } from "@/components/overview-cards"
import { SessionsTable } from "@/components/sessions-table"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ApiUnreachableError, fetchSessions } from "@/lib/api"

export default async function SessionsPage() {
  let data
  try {
    data = await fetchSessions()
  } catch (error) {
    if (error instanceof ApiUnreachableError) {
      return (
        <DashboardShell title="Sessions">
          <ApiError message={error.message} />
        </DashboardShell>
      )
    }
    throw error
  }

  const { sessions, unreadable, disclaimers } = data

  return (
    <DashboardShell title="Sessions">
      <SectionHeader
        as="h1"
        title="Screening sessions"
        description="Every recorded run of the VOMS visual motion subtest, newest first. Open a session for its full metrics and exercise suggestions."
        actions={
          <Button render={<Link href="/capture" />}>
            <VideoIcon className="size-4" />
            New session
          </Button>
        }
      />

      {sessions.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <OverviewCards sessions={sessions} />
          <ScreeningDisclaimer text={disclaimers.screening} />
          <Section title="All sessions">
            <SessionsTable sessions={sessions} />
          </Section>
        </>
      )}

      {/* Files that could not be parsed are surfaced rather than skipped: a session
          silently missing from this list is worse than a visible error. */}
      {unreadable.length > 0 ? (
        <Card className="border-destructive/40 bg-destructive/[0.03]">
          <CardContent className="space-y-2 py-4">
            <p className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangleIcon className="size-4 text-destructive" />
              {unreadable.length} file{unreadable.length === 1 ? "" : "s"} could not
              be read
            </p>
            <ul className="space-y-1 text-xs text-muted-foreground">
              {unreadable.map((entry) => (
                <li key={entry.id}>
                  <code className="rounded bg-muted px-1 py-0.5">{entry.id}</code>{" "}
                  {entry.error}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </DashboardShell>
  )
}

function EmptyState() {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-4 py-14 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-primary/10">
          <VideoIcon className="size-5 text-primary" />
        </span>
        <div className="space-y-1.5">
          <p className="font-heading text-lg font-semibold">No sessions yet</p>
          <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
            Record one from the browser, or run it from the command line with{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              python run_session.py --score
            </code>
            .
          </p>
        </div>
        <Button render={<Link href="/capture" />}>
          <VideoIcon className="size-4" />
          Record a session
        </Button>
      </CardContent>
    </Card>
  )
}
