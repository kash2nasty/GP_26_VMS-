/**
 * Segmented meter showing where a composite score falls across the four tiers.
 *
 * A bare "75.36 / 100" tells you almost nothing without the thresholds beside it,
 * and a plain progress bar would imply a smooth scale that the scoring layer
 * deliberately does not claim: the output is four bands, and the bands are not
 * equal widths (0-20, 20-40, 40-65, 65-100). Drawing the segments proportionally
 * shows both the band you landed in and how close you sat to the next one.
 *
 * Segment widths come from the thresholds the API reports, not from constants
 * duplicated here, so retuning them in Python moves this meter too.
 */

import type { SeverityTier } from "@/lib/api"
import { TIER_ORDER } from "@/lib/format"

const FALLBACK_THRESHOLDS: Record<string, number> = {
  minimal: 0,
  mild: 20,
  moderate: 40,
  pronounced: 65,
}

const SEGMENT_FILL: Record<SeverityTier, string> = {
  minimal: "bg-slate-400/70 dark:bg-slate-500/70",
  mild: "bg-sky-400/80 dark:bg-sky-500/70",
  moderate: "bg-amber-400/85 dark:bg-amber-500/75",
  pronounced: "bg-orange-500/85 dark:bg-orange-500/80",
}

export function TierMeter({
  composite,
  tier,
  thresholds,
}: {
  composite: number | null | undefined
  tier: SeverityTier | null | undefined
  thresholds?: Record<string, number>
}) {
  const lower = { ...FALLBACK_THRESHOLDS, ...(thresholds ?? {}) }

  // Each band runs from its own lower bound to the next tier's lower bound.
  const bands = TIER_ORDER.map((name, index) => {
    const start = lower[name] ?? 0
    const next = TIER_ORDER[index + 1]
    const end = next ? (lower[next] ?? 100) : 100
    return { name, start, end, width: Math.max(0, end - start) }
  })

  const total = bands.reduce((sum, band) => sum + band.width, 0) || 100
  const hasScore = typeof composite === "number" && Number.isFinite(composite)
  const markerPercent = hasScore
    ? Math.min(100, Math.max(0, (composite / total) * 100))
    : null

  return (
    <div className="space-y-2">
      <div className="relative">
        <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full">
          {bands.map((band) => {
            const active = band.name === tier
            return (
              <div
                key={band.name}
                style={{ width: `${(band.width / total) * 100}%` }}
                className={`h-full transition-opacity ${
                  active
                    ? SEGMENT_FILL[band.name]
                    : "bg-muted opacity-70"
                }`}
              />
            )
          })}
        </div>

        {markerPercent !== null ? (
          <div
            className="absolute -top-1 h-4.5 w-0.5 rounded-full bg-foreground transition-[left]"
            style={{ left: `calc(${markerPercent}% - 1px)` }}
            aria-hidden="true"
          />
        ) : null}
      </div>

      <div className="flex justify-between text-[0.7rem] font-medium">
        {bands.map((band) => (
          <span
            key={band.name}
            className={`capitalize ${
              band.name === tier ? "text-foreground" : "text-muted-foreground/70"
            }`}
          >
            {band.name}
          </span>
        ))}
      </div>
    </div>
  )
}

/** Completed repetitions as dots, so progress reads without parsing "5 / 5". */
export function RepDots({
  completed,
  target,
}: {
  completed: number | null | undefined
  target: number | null | undefined
}) {
  const done = typeof completed === "number" ? completed : 0
  const goal = typeof target === "number" && target > 0 ? target : 5
  const shown = Math.max(goal, done)

  return (
    <div className="flex flex-wrap items-center gap-1" aria-hidden="true">
      {Array.from({ length: Math.min(shown, 20) }, (_, index) => (
        <span
          key={index}
          className={`size-2 rounded-full ${
            index < done
              ? index < goal
                ? "bg-primary"
                : "bg-primary/50"
              : "bg-muted-foreground/25"
          }`}
        />
      ))}
    </div>
  )
}
