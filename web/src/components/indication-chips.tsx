/**
 * Compact indication summary for a table row.
 *
 * The list view cannot afford twelve entries per session, so it shows a count and
 * the ids of what was flagged. Ids rather than a bare number, because "2 flagged"
 * tells a reader to open the session while "eyelid asymmetry, low blink rate" often
 * tells them they do not need to.
 *
 * Sessions whose panel was computed on read rather than stored are not marked here.
 * That distinction matters on the detail page, where the numbers are, and it would
 * be noise in a row that has room for about six words.
 */

import { Badge } from "@/components/ui/badge"

/** Short labels, since the full ones do not fit a table cell. */
const SHORT_LABELS: Record<string, string> = {
  visual_motion_sensitivity: "motion sensitivity",
  vestibular_asymmetry: "one-sided instability",
  rhythmic_eye_oscillation: "eye oscillation",
  fixation_breakdown: "fixation breaks",
  horizontal_ocular_misalignment: "horizontal alignment",
  vertical_ocular_misalignment: "vertical alignment",
  eyelid_asymmetry: "eyelid asymmetry",
  fatigable_eyelid_droop: "fatigable droop",
  blink_rate_abnormality: "blink rate",
  facial_asymmetry: "facial asymmetry",
  cervical_rotation_restriction: "neck rotation",
  head_tremor: "head tremor",
}

export function shortIndicationLabel(id: string): string {
  return SHORT_LABELS[id] ?? id.replace(/_/g, " ")
}

export function IndicationChips({
  indicated,
  notAssessable,
  checksRun,
  max = 2,
}: {
  indicated?: string[]
  notAssessable?: number
  checksRun?: number | null
  max?: number
}) {
  if (!checksRun) {
    return <span className="text-xs text-muted-foreground">Not assessed</span>
  }

  const flagged = indicated ?? []
  const assessed = checksRun - (notAssessable ?? 0)

  if (flagged.length === 0) {
    // "None of 11" implies eleven checks ran and found nothing, which is exactly
    // wrong when all eleven could not be run. Captures made before the wider
    // signal set existed are all in that position, so this is the common case
    // rather than an edge one.
    return (
      <span className="text-xs text-muted-foreground">
        {assessed <= 0
          ? "Nothing assessable"
          : `None flagged of ${assessed}`}
        {notAssessable ? (
          <span className="text-muted-foreground/70">
            {assessed <= 0 ? "" : `, ${notAssessable} n/a`}
          </span>
        ) : null}
      </span>
    )
  }

  const shown = flagged.slice(0, max)
  const hidden = flagged.length - shown.length

  return (
    <span className="flex flex-wrap items-center gap-1">
      {shown.map((id) => (
        <Badge
          key={id}
          variant="outline"
          className="border-amber-400/70 bg-amber-100/70 text-[0.68rem] text-amber-950 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-100"
        >
          {shortIndicationLabel(id)}
        </Badge>
      ))}
      {hidden > 0 ? (
        <span className="text-[0.68rem] text-muted-foreground">
          +{hidden} more
        </span>
      ) : null}
    </span>
  )
}
