/**
 * Metric display for the detail page.
 *
 * Every metric carries a plain-language explanation beside the number. The raw
 * field names (`residual_rms_offset_units`, `compensation_r2`) mean nothing on their
 * own, and a dashboard that shows them bare invites the reader to invent an
 * interpretation.
 *
 * WHAT CHANGED IN THE SPACING, AND WHY IT WAS THE MAIN PROBLEM
 *     The number used to sit on the same row as its label, hard right, with the
 *     explanation underneath spanning the full card. On a wide card that put two or
 *     three words on the left, five characters on the right, and forty centimetres
 *     of nothing between them, repeated eight times. It also gave the number and
 *     the label equal visual weight, so the eye had nothing to land on.
 *
 *     Now each row is a two-column grid: the number occupies a fixed right-hand
 *     column of consistent width, so numbers line up down the card as a column
 *     rather than raggedly tracking whatever the label length happens to be. The
 *     explanation sits under the label only, inside the left column, so it is
 *     visibly subordinate to it and its line length stays readable.
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export type Metric = {
  label: string
  value: string
  /** What the number means in plain language. */
  help?: string
  /** Set when the underlying value was missing or unusable. */
  muted?: boolean
}

export function MetricRow({ metric }: { metric: Metric }) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 gap-y-1 border-b border-border/50 py-2.5 first:pt-0 last:border-b-0 last:pb-0">
      <p className="text-sm leading-snug font-medium">{metric.label}</p>
      <p
        className={`min-w-[5.5rem] text-right font-mono text-sm font-semibold tabular-nums ${
          metric.muted ? "text-muted-foreground" : "text-foreground"
        }`}
      >
        {metric.value}
      </p>
      {metric.help ? (
        <p className="col-start-1 max-w-[54ch] text-xs leading-relaxed text-muted-foreground">
          {metric.help}
        </p>
      ) : null}
    </div>
  )
}

export function MetricCard({
  title,
  description,
  metrics,
  footer,
  accent,
}: {
  title: string
  description?: string
  metrics: Metric[]
  footer?: React.ReactNode
  /** Marks the card that carries the primary signal. */
  accent?: boolean
}) {
  return (
    <Card className={accent ? "ring-primary/30" : undefined}>
      <CardHeader>
        <CardTitle className="text-[0.95rem]">{title}</CardTitle>
        {description ? (
          <CardDescription className="max-w-[58ch] text-xs leading-relaxed">
            {description}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent>
        {metrics.map((metric) => (
          <MetricRow key={metric.label} metric={metric} />
        ))}
        {footer ? <div className="pt-3">{footer}</div> : null}
      </CardContent>
    </Card>
  )
}

/** Compact label and value pair for the hero area. */
export function KeyFact({
  label,
  value,
  detail,
}: {
  label: string
  value: React.ReactNode
  detail?: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <p className="eyebrow">{label}</p>
      <div className="text-base leading-none font-semibold">{value}</div>
      {detail ? (
        <p className="text-xs leading-relaxed text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  )
}
