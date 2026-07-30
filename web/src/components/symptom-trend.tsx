"use client"

/**
 * Self-reported symptom score across sessions.
 *
 * WHY THIS METRIC AND NOT THE COMPOSITE SCORE
 *     overview-cards.tsx refuses to average or trend the composite, and it is
 *     right to: the objective half of that number is uncalibrated and moves with
 *     how fast the head was rotated, which is not controlled between captures, so
 *     a trend line would look like a measurement while being an artifact of
 *     inconsistent technique.
 *
 *     The symptom score has none of that problem. It is the same question, on the
 *     same 0 to 10 scale, and in the clinical protocol it IS the outcome measure.
 *     Plotting it is the one honest trend available here.
 *
 * WHAT THE MARKERS SAY
 *     A session with no symptom score is a gap in the line rather than a zero,
 *     because 0 means "no symptoms" and is a real result. Sessions where the
 *     camera signal failed its gates are drawn as hollow points: the symptom
 *     number is still valid, but the reader should know the tier beside it rested
 *     on that number alone.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import type { SessionSummary } from "@/lib/api"
import { formatDateOnly, formatDateTime, isPresent } from "@/lib/format"

/** Mucha et al. 2014: 2 or above on any VOMS item is a positive screen. */
const POSITIVE_SCREEN_CUTOFF = 2

export function SymptomTrend({ sessions }: { sessions: SessionSummary[] }) {
  // Sessions are usually recorded in bursts on the same day, so a date-only axis
  // printed the identical label under every point and told the reader nothing. The
  // tick shows the time when a date repeats, and the tooltip always shows both.
  const dayCounts = new Map<string, number>()
  for (const session of sessions) {
    const day = formatDateOnly(session.captured_at)
    dayCounts.set(day, (dayCounts.get(day) ?? 0) + 1)
  }

  // Oldest first, so time runs left to right. The API sends newest first.
  const points = [...sessions].reverse().map((session, index) => {
    const day = formatDateOnly(session.captured_at)
    const full = formatDateTime(session.captured_at)
    return {
      index,
      // "29 Jul 2026, 15:48" becomes "15:48" on a day with several captures.
      tick: (dayCounts.get(day) ?? 0) > 1 ? full.split(", ").pop() ?? day : day,
      label: full,
      symptom: isPresent(session.symptom_score) ? session.symptom_score : null,
      cameraUsed: session.objective_signal_usable === true,
      tier: session.severity_tier ?? "no tier",
    }
  })

  const scored = points.filter((point) => point.symptom !== null)
  if (scored.length < 2) return null

  return (
    <ChartContainer
      config={{
        symptom: { label: "Reported symptoms", color: "var(--chart-1)" },
      }}
      className="aspect-auto h-[168px] w-full"
    >
      <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="tick"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={16}
        />
        <YAxis
          domain={[0, 10]}
          ticks={[0, 2, 5, 10]}
          tickLine={false}
          axisLine={false}
          tickMargin={4}
          width={40}
        />
        <ReferenceLine
          y={POSITIVE_SCREEN_CUTOFF}
          stroke="var(--chart-4)"
          strokeDasharray="4 4"
          label={{
            value: "positive screen cut-off",
            position: "insideTopRight",
            fill: "var(--muted-foreground)",
            fontSize: 10,
          }}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelKey="label"
              formatter={(value, _name, item) => (
                <span className="flex w-full justify-between gap-4">
                  <span className="text-muted-foreground">
                    {item?.payload?.tier}
                    {item?.payload?.cameraUsed ? "" : ", symptoms only"}
                  </span>
                  <span className="font-mono tabular-nums">{value} / 10</span>
                </span>
              )}
            />
          }
        />
        <Line
          dataKey="symptom"
          type="monotone"
          stroke="var(--chart-1)"
          strokeWidth={2}
          // Gaps rather than zeros where no score was reported.
          connectNulls={false}
          dot={({ cx, cy, payload, key }) =>
            payload.symptom === null ? (
              <g key={key} />
            ) : (
              <circle
                key={key}
                cx={cx}
                cy={cy}
                r={3.5}
                strokeWidth={2}
                stroke="var(--chart-1)"
                fill={payload.cameraUsed ? "var(--chart-1)" : "var(--card)"}
              />
            )
          }
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ChartContainer>
  )
}
