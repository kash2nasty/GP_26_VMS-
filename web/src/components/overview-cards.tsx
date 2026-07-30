/**
 * Summary strip for the list page.
 *
 * WHAT THESE DELIBERATELY DO NOT SHOW
 *     Any average or trend of the composite score. The objective half of that
 *     score is uncalibrated and moves with how fast the head was rotated, which is
 *     not controlled between captures, so an average would look like a measurement
 *     while being an artifact of inconsistent technique. Counts and the latest
 *     single reading are defensible; a cross-session aggregate of that metric is
 *     not. The one thing that IS trended, in symptom-trend.tsx, is the
 *     self-reported score, which has no such problem.
 *
 * LAYOUT NOTE
 *     Four equal cards in a row was the previous arrangement and it gave the same
 *     weight to "how many sessions exist" as to "what did the last one say". The
 *     latest result now takes a wide cell with the wash treatment, and the three
 *     supporting counts share the rest. That is the only hierarchy this strip needs,
 *     and without it the strip was four identical boxes, which is exactly the look
 *     the redesign was meant to remove.
 */

import { TierBadge } from "@/components/tier-badge"
import { Card, CardContent } from "@/components/ui/card"
import type { SessionSummary } from "@/lib/api"
import { formatDateOnly, isPresent } from "@/lib/format"

function Stat({
  label,
  value,
  hint,
}: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
}) {
  return (
    <Card size="sm" className="justify-center">
      <CardContent className="space-y-1">
        <p className="eyebrow">{label}</p>
        <div className="text-xl leading-none font-semibold tabular-nums">
          {value}
        </div>
        {hint ? (
          <p className="text-xs leading-snug text-muted-foreground">{hint}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function OverviewCards({ sessions }: { sessions: SessionSummary[] }) {
  const latest = sessions[0]
  const usable = sessions.filter((s) => s.objective_signal_usable === true).length
  const offProtocol = sessions.filter(
    (s) => s.comparable_to_clinical_protocol === false
  ).length
  const scored = sessions.filter((s) => isPresent(s.symptom_score)).length
  const flagged = sessions.filter(
    (s) => (s.indications_indicated?.length ?? 0) > 0
  ).length
  // Sessions where every check beyond the subtest came back not assessable. Every
  // capture made before the wider signal set existed is in this position, and
  // reporting "0 flagged" for them without saying so would read as a clean result
  // when nothing was actually looked at.
  const noneAssessable = sessions.filter(
    (s) =>
      (s.indications_checks_run ?? 0) > 0 &&
      (s.indications_checks_run ?? 0) - (s.indications_not_assessable ?? 0) <= 0
  ).length

  return (
    <div className="grid gap-3 @2xl/main:grid-cols-2 @4xl/main:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <Card className="hero-wash justify-center ring-primary/25">
        <CardContent className="space-y-2.5">
          <p className="eyebrow">Latest session</p>
          <div className="flex flex-wrap items-center gap-2.5">
            {latest ? (
              <TierBadge
                tier={latest.severity_tier}
                className="px-2.5 py-0.5 text-sm"
              />
            ) : (
              <span className="text-xl font-semibold">n/a</span>
            )}
            {latest && isPresent(latest.symptom_score) ? (
              <span className="font-mono text-sm text-muted-foreground tabular-nums">
                symptoms {latest.symptom_score} / 10
              </span>
            ) : null}
          </div>
          <p className="text-xs leading-snug text-muted-foreground">
            {latest?.captured_at
              ? `Recorded ${formatDateOnly(latest.captured_at)}. `
              : "None recorded yet. "}
            {latest
              ? latest.objective_signal_usable
                ? "Symptom report and camera signal both used."
                : "Symptom report only; the camera signal was not usable."
              : ""}
          </p>
        </CardContent>
      </Card>

      <Stat
        label="Sessions"
        value={sessions.length}
        hint={`${scored} carry a symptom score`}
      />
      <Stat
        label="Indications flagged"
        value={
          <>
            {flagged}
            <span className="text-base font-normal text-muted-foreground">
              {" "}
              / {sessions.length}
            </span>
          </>
        }
        hint={
          noneAssessable === sessions.length
            ? `No capture supports these checks yet. Record a new session to run them.`
            : flagged > 0
              ? "Sessions with at least one signal to review"
              : noneAssessable > 0
                ? `${noneAssessable} could not be assessed at all`
                : "No session has a flagged signal"
        }
      />
      <Stat
        label="Camera signal used"
        value={
          <>
            {usable}
            <span className="text-base font-normal text-muted-foreground">
              {" "}
              / {sessions.length}
            </span>
          </>
        }
        hint={
          offProtocol > 0
            ? `${offProtocol} off protocol`
            : sessions.length > 0
              ? "All within protocol"
              : undefined
        }
      />
    </div>
  )
}
