/**
 * The screening indications panel.
 *
 * This is the surface for scoring/indications.py, and its whole design problem is
 * that the panel must be readable without ever reading as a diagnosis. Four
 * decisions follow from that:
 *
 * 1. NO GREEN, ANYWHERE. A green "nothing flagged" chip is an all-clear, and the
 *    scoring layer is explicit that a negative result means one measurement did not
 *    cross one provisional threshold in one session. Slate carries "no signal"
 *    without carrying "you are fine".
 *
 * 2. "COULD NOT BE ASSESSED" IS NOT A QUIET PASS. It gets its own group, its own
 *    dashed treatment, and it is placed ABOVE the negative results rather than
 *    buried under them, because it is the more actionable of the two: it usually
 *    names something the operator can fix and recapture.
 *
 * 3. EVERY FLAGGED ENTRY SHOWS ITS OWN COUNTER-ARGUMENT. The caveat is not tucked
 *    into a tooltip. It sits in the expanded body next to the measurement, because
 *    for most of these checks the mundane explanation is more likely than the
 *    clinical one and the reader has to see both to weigh them.
 *
 * 4. WHAT IT SCREENS FOR IS PHRASED AS A LIST OF ASSOCIATIONS, never as a
 *    conclusion. The heading of each entry is the observation ("Rhythmic eye
 *    oscillation"), and the conditions appear underneath as things that pattern is
 *    associated with.
 *
 * Expansion uses native <details>, so the panel is a Server Component with no
 * client JavaScript and every entry is open to Ctrl+F and to print.
 */

import {
  ActivityIcon,
  CircleAlertIcon,
  CircleSlashIcon,
  MinusIcon,
  TriangleAlertIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { Finding, Indication, IndicationPanel } from "@/lib/api"
import {
  EVIDENCE_LABELS,
  FINDING_LABELS,
  FINDING_ORDER,
  FINDING_STYLES,
  STRENGTH_LABELS,
  URGENCY_LABELS,
  URGENCY_STYLES,
  formatMeasured,
  humanizeKey,
} from "@/lib/format"

const GROUP_META: Record<
  Finding,
  { title: string; blurb: string; icon: typeof ActivityIcon }
> = {
  indicated: {
    title: "Flagged for review",
    blurb:
      "A measurement crossed its threshold. That is a reason to look, not a finding.",
    icon: TriangleAlertIcon,
  },
  not_assessable: {
    title: "Could not be assessed",
    blurb:
      "This capture could not support these checks. Most of them say what to change and recapture.",
    icon: CircleSlashIcon,
  },
  not_indicated: {
    title: "Nothing flagged",
    blurb:
      "One measurement did not cross one provisional threshold in one session. Not a clearance.",
    icon: MinusIcon,
  },
}

export function IndicationSummary({ panel }: { panel: IndicationPanel }) {
  // The count shown is of checks BEYOND the subtest. The primary check is the
  // severity tier, which the hero directly above this already states, so counting
  // it here would report the same result twice on one screen.
  const flagged = (panel.secondary_indicated ?? panel.indicated).length
  const total = panel.secondary_checks_run ?? panel.checks_run ?? panel.panel.length
  const urgent = panel.highest_urgency

  return (
    <Card
      className={
        flagged > 0
          ? "ring-amber-400/50 dark:ring-amber-700/60"
          : undefined
      }
    >
      <CardContent className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <span
          className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${
            flagged > 0
              ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
              : "bg-surface-strong text-muted-foreground"
          }`}
          aria-hidden="true"
        >
          {flagged > 0 ? (
            <TriangleAlertIcon className="size-4.5" />
          ) : (
            <ActivityIcon className="size-4.5" />
          )}
        </span>

        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm leading-snug font-medium">{panel.summary}</p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {panel.method?.what_an_indication_means}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Counter label="Flagged" value={flagged} emphasis={flagged > 0} />
          <Counter label="Not assessable" value={panel.not_assessable.length} />
          <Counter label="Checks run" value={total} />
        </div>

        {/* Inline, not a full-width bar. As a bar it read as a page-level error
            banner and said the same thing as the note immediately below it. */}
        {urgent && urgent !== "routine" ? (
          <Badge
            variant="outline"
            className={`gap-1.5 ${URGENCY_STYLES[urgent]}`}
          >
            <CircleAlertIcon className="size-3.5" />
            {URGENCY_LABELS[urgent]}
          </Badge>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Counter({
  label,
  value,
  emphasis = false,
}: {
  label: string
  value: number
  emphasis?: boolean
}) {
  return (
    <div
      className={`rounded-lg px-3 py-1.5 text-center ${
        emphasis
          ? "bg-amber-100 text-amber-950 dark:bg-amber-950/70 dark:text-amber-100"
          : "bg-surface-strong"
      }`}
    >
      <p className="font-mono text-lg leading-none font-semibold tabular-nums">
        {value}
      </p>
      <p className="mt-1 text-[0.62rem] tracking-wide uppercase opacity-70">
        {label}
      </p>
    </div>
  )
}

export function IndicationList({ panel }: { panel: IndicationPanel }) {
  const grouped = FINDING_ORDER.map((finding) => ({
    finding,
    entries: panel.panel.filter((entry) => entry.finding === finding),
  })).filter((group) => group.entries.length > 0)

  return (
    <div className="space-y-6">
      {panel.emergency_note ? (
        <div className="rounded-lg border border-rose-300/80 bg-rose-50/70 px-4 py-3 dark:border-rose-900/70 dark:bg-rose-950/25">
          <p className="flex items-center gap-2 text-[0.7rem] font-semibold tracking-wider uppercase text-rose-900 dark:text-rose-200">
            <CircleAlertIcon className="size-3.5" />
            If any of this is new
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-rose-950/90 dark:text-rose-100/90">
            {panel.emergency_note}
          </p>
        </div>
      ) : null}

      {grouped.map(({ finding, entries }) => {
        const meta = GROUP_META[finding]
        return (
          <section key={finding} className="space-y-2.5">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="flex items-center gap-2 text-[0.95rem] font-semibold">
                <meta.icon className="size-4 text-muted-foreground" />
                {meta.title}
                <span className="font-mono text-xs font-normal text-muted-foreground tabular-nums">
                  {entries.length}
                </span>
              </h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {meta.blurb}
              </p>
            </div>
            <div className="space-y-2">
              {entries.map((entry) => (
                <IndicationRow key={entry.id} indication={entry} />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function IndicationRow({ indication }: { indication: Indication }) {
  const flagged = indication.finding === "indicated"
  const measured = Object.entries(indication.measured ?? {})
  const thresholds = Object.entries(indication.thresholds ?? {})

  return (
    <details
      className={`group overflow-hidden rounded-lg ring-1 transition-colors ${
        flagged
          ? "bg-amber-50/50 ring-amber-300/70 hover:bg-amber-50 dark:bg-amber-950/20 dark:ring-amber-900/70"
          : "bg-card ring-foreground/10 hover:bg-surface"
      }`}
      // Flagged entries start open. Anything the panel wants read should not
      // require a click to discover it.
      open={flagged}
    >
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{indication.label}</span>
          <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
            Screens for {joinAssociations(indication.screens_for)}
          </span>
        </span>

        {indication.strength ? (
          <Badge
            variant="outline"
            className={FINDING_STYLES[indication.finding]}
          >
            {STRENGTH_LABELS[indication.strength]}
          </Badge>
        ) : (
          <Badge
            variant="outline"
            className={FINDING_STYLES[indication.finding]}
          >
            {FINDING_LABELS[indication.finding]}
          </Badge>
        )}

        {flagged && indication.urgency !== "routine" ? (
          <Badge
            variant="outline"
            className={URGENCY_STYLES[indication.urgency]}
          >
            {URGENCY_LABELS[indication.urgency]}
          </Badge>
        ) : null}

        {/* Marks the entry that restates the severity tier, so a reader does not
            read it as an extra finding on top of it. */}
        {indication.is_primary ? (
          <Badge variant="secondary" className="text-[0.65rem]">
            The subtest itself
          </Badge>
        ) : null}
      </summary>

      <div className="space-y-4 px-4 pb-4 text-sm">
        <p className="max-w-[68ch] leading-relaxed">
          {indication.interpretation || indication.reason}
        </p>

        {measured.length > 0 || thresholds.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {measured.length > 0 ? (
              <ValueTable title="Measured" rows={measured} />
            ) : null}
            {thresholds.length > 0 ? (
              <ValueTable title="Compared against" rows={thresholds} />
            ) : null}
          </div>
        ) : null}

        {indication.caveat ? (
          <div className="inset-panel px-3.5 py-3">
            <p className="eyebrow">What else explains this</p>
            <p className="mt-1 max-w-[68ch] text-xs leading-relaxed text-muted-foreground">
              {indication.caveat}
            </p>
          </div>
        ) : null}

        {indication.next_step ? (
          <div>
            <p className="eyebrow">What actually answers the question</p>
            <p className="mt-1 max-w-[68ch] text-xs leading-relaxed text-muted-foreground">
              {indication.next_step}
            </p>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 border-t pt-3">
          <Badge variant="secondary" className="text-[0.65rem]">
            {EVIDENCE_LABELS[indication.evidence_basis] ??
              indication.evidence_basis}
          </Badge>
          {(indication.references ?? []).map((reference) => (
            <span
              key={reference}
              className="text-[0.68rem] leading-snug text-muted-foreground"
            >
              {reference}
            </span>
          ))}
        </div>
      </div>
    </details>
  )
}

function ValueTable({
  title,
  rows,
}: {
  title: string
  rows: Array<[string, number | string | number[] | null | undefined]>
}) {
  return (
    <div className="inset-panel overflow-hidden">
      <p className="eyebrow px-3.5 pt-2.5 pb-1.5">{title}</p>
      <dl className="divide-y divide-border/60">
        {rows.map(([key, value]) => (
          <div
            key={key}
            className="flex items-baseline justify-between gap-4 px-3.5 py-1.5"
          >
            <dt className="text-xs text-muted-foreground">{humanizeKey(key)}</dt>
            <dd className="shrink-0 font-mono text-xs font-medium tabular-nums">
              {formatMeasured(value)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

/** "a, b or c", so the list never reads as a set of conclusions. */
function joinAssociations(items: string[]): string {
  if (items.length === 0) return "nothing specific"
  if (items.length === 1) return items[0]
  return `${items.slice(0, -1).join(", ")} or ${items[items.length - 1]}`
}
