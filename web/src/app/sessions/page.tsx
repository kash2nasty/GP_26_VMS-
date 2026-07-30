import Link from "next/link"
import { AlertTriangleIcon, TrendingUpIcon, VideoIcon } from "lucide-react"

import { ApiError } from "@/components/api-error"
import { DashboardShell, Section, SectionHeader } from "@/components/dashboard-shell"
import { ScreeningDisclaimer } from "@/components/disclaimer"
import { OverviewCards } from "@/components/overview-cards"
import { SessionsTable } from "@/components/sessions-table"
import { SymptomTrend } from "@/components/symptom-trend"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ApiUnreachableError, fetchSessions } from "@/lib/api"
import { isPresent } from "@/lib/format"

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
  const scoredCount = sessions.filter((s) => isPresent(s.symptom_score)).length

  return (
    <DashboardShell title="Sessions">
      <SectionHeader
        as="h1"
        eyebrow="Screening sessions"
        title="Every capture, newest first"
        description="Each session is one run of the VOMS visual-motion subtest. Open a session for its full measurements, the screening indications derived from them, and exercise suggestions."
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

          {/* Two or more scored sessions before a trend means anything, and
              SymptomTrend returns null below that rather than drawing a line
              through one point. */}
          {scoredCount >= 2 ? (
            <Section
              title="Reported symptoms over time"
              description="The self-reported 0 to 10 provocation score, which is the outcome measure the clinical protocol is built around. Hollow points mark sessions where the camera signal failed its quality gates, so the tier rested on this number alone."
            >
              <Card>
                <CardContent>
                  <SymptomTrend sessions={sessions} />
                </CardContent>
              </Card>
            </Section>
          ) : null}

          <ScreeningDisclaimer text={disclaimers.screening} />

          <Section
            title="All sessions"
            description="Sort by any of the first four columns. Select rows to delete several at once."
          >
            <SessionsTable sessions={sessions} />
          </Section>
        </>
      )}

      {/* Files that could not be parsed are surfaced rather than skipped: a session
          silently missing from this list is worse than a visible error. */}
      {unreadable.length > 0 ? (
        <Card className="bg-destructive/[0.03] ring-destructive/40">
          <CardContent className="space-y-2">
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
    <Card className="hero-wash border-dashed">
      <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
        <span className="flex size-12 items-center justify-center rounded-xl bg-linear-to-br from-primary to-chart-3 text-primary-foreground shadow-sm">
          <TrendingUpIcon className="size-5" />
        </span>
        <div className="space-y-1.5">
          <p className="font-heading text-lg font-semibold">No sessions yet</p>
          <p className="mx-auto max-w-[52ch] text-sm leading-relaxed text-muted-foreground">
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
