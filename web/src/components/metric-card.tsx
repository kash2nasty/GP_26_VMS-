/**
 * Metric display for the detail page.
 *
 * Every metric carries a plain-language explanation next to the number. The raw
 * field names (`residual_rms_offset_units`, `compensation_r2`) mean nothing on
 * their own, and a dashboard that shows them bare invites the reader to invent an
 * interpretation.
 *
 * Layout note: the value sits on the same baseline as the label with the
 * explanation beneath, rather than label-left / value-right on one row. With help
 * text present, the split-row version left a ragged column of numbers floating
 * beside paragraphs of different heights.
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
    <div className="border-b border-border/60 py-2.5 last:border-b-0 first:pt-0">
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-sm font-medium">{metric.label}</p>
        <p
          className={`shrink-0 font-mono text-sm font-semibold tabular-nums ${
            metric.muted ? "text-muted-foreground" : "text-foreground"
          }`}
        >
          {metric.value}
        </p>
      </div>
      {metric.help ? (
        <p className="mt-1 max-w-prose text-xs leading-relaxed text-muted-foreground">
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
    <Card className={accent ? "border-primary/30" : undefined}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        {description ? (
          <CardDescription className="leading-relaxed">
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

/** Compact label/value pair for the hero area. */
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
      <p className="text-[0.7rem] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <div className="text-lg font-semibold leading-none">{value}</div>
      {detail ? (
        <p className="text-xs leading-relaxed text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  )
}
