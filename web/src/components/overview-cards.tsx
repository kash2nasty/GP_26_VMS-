/**
 * Summary strip for the list page.
 *
 * What these deliberately do NOT show: any average or trend of the composite
 * score. The objective half of that score is uncalibrated and sensitive to how
 * fast the head was rotated, which is not controlled between captures, so an
 * average would look like a measurement while being an artifact of inconsistent
 * technique. Counts and the latest single reading are defensible; a cross-session
 * aggregate of that metric is not.
 */

import { Card, CardContent } from "@/components/ui/card"
import { TierBadge } from "@/components/tier-badge"
import type { SessionSummary } from "@/lib/api"
import { formatDateOnly, isPresent } from "@/lib/format"

function Stat({
  label,
  value,
  hint,
  accent = false,
}: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  accent?: boolean
}) {
  return (
    <Card
      className={`relative overflow-hidden ${
        accent ? "border-primary/30 bg-primary/[0.04]" : ""
      }`}
    >
      {/* A thin accent rail rather than a full gradient fill: it marks the card
          without tinting the text background. */}
      <span
        className={`absolute inset-y-0 left-0 w-0.5 ${
          accent ? "bg-primary" : "bg-border"
        }`}
        aria-hidden="true"
      />
      <CardContent className="space-y-1.5 py-4 pl-5">
        <p className="text-[0.7rem] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <div className="text-2xl font-semibold leading-none tabular-nums">
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

  return (
    <div className="grid grid-cols-2 gap-3 @3xl/main:grid-cols-4">
      <Stat
        label="Sessions"
        value={sessions.length}
        hint={
          latest?.captured_at
            ? `Latest ${formatDateOnly(latest.captured_at)}`
            : "None recorded yet"
        }
      />
      <Stat
        label="Latest tier"
        accent
        value={
          latest ? (
            <TierBadge tier={latest.severity_tier} className="text-sm" />
          ) : (
            "n/a"
          )
        }
        hint={
          latest
            ? latest.objective_signal_usable
              ? "Symptom report plus camera signal"
              : "Symptom report only"
            : undefined
        }
      />
      <Stat
        label="Latest symptoms"
        value={
          latest && isPresent(latest.symptom_score) ? (
            <>
              {latest.symptom_score}
              <span className="text-base font-normal text-muted-foreground">
                {" "}
                / 10
              </span>
            </>
          ) : (
            "Not reported"
          )
        }
        hint={
          sessions.length > 0
            ? `${scored} of ${sessions.length} sessions scored`
            : undefined
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
