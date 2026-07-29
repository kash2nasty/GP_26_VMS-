import { notFound } from "next/navigation"

import { ApiError } from "@/components/api-error"
import { DashboardShell, Section, SectionHeader } from "@/components/dashboard-shell"
import { DeleteSessionButton } from "@/components/delete-session-button"
import { ScreeningDisclaimer, SessionDisclaimer } from "@/components/disclaimer"
import { ExerciseList } from "@/components/exercise-list"
import { KeyFact, MetricCard, type Metric } from "@/components/metric-card"
import { RepDots, TierMeter } from "@/components/tier-meter"
import { ObjectiveSignalBadge, ProtocolBadge, TierBadge } from "@/components/tier-badge"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ApiUnreachableError, fetchSession } from "@/lib/api"
import {
  degrees,
  formatDateTime,
  humanizeFlag,
  int,
  isPresent,
  num,
  percent,
  seconds,
  statusLabel,
} from "@/lib/format"

/**
 * `params` is a Promise in Next.js 16: synchronous access was fully removed in
 * this major version, so it must be awaited.
 */
export default async function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  let detail
  try {
    detail = await fetchSession(id)
  } catch (error) {
    if (error instanceof ApiUnreachableError) {
      return (
        <DashboardShell title="Session" backHref="/sessions" backLabel="Sessions">
          <ApiError message={error.message} />
        </DashboardShell>
      )
    }
    throw error
  }

  if (!detail) notFound()

  const { session, summary, disclaimers } = detail
  const screening = session.screening_summary
  const gaze = session.gaze_stability
  const head = session.head_motion
  const tracking = session.tracking_quality
  const fidelity = screening?.protocol_fidelity
  const objectiveUsable = screening?.data_quality?.objective_signal_usable
  const recordedAt = formatDateTime(detail.captured_at)

  const gazeMetrics: Metric[] = [
    {
      label: "Fixation stability",
      value: isPresent(gaze?.fixation_stability_score)
        ? `${num(gaze?.fixation_stability_score, 1)} / 100`
        : "n/a",
      help: "Higher is steadier. 100 would mean every eye movement was explained by smooth compensation for head rotation.",
      muted: !isPresent(gaze?.fixation_stability_score),
    },
    {
      label: "Compensation fit (r squared)",
      value: num(gaze?.compensation_r2, 4),
      help: "How closely the eyes counter rotated in proportion to the head. Near 1.0 means smooth compensation. A low value is ambiguous: it can mean poor fixation or unreliable tracking.",
      muted: !isPresent(gaze?.compensation_r2),
    },
    {
      label: "Unexplained eye motion (RMS)",
      value: num(gaze?.residual_rms_offset_units, 5),
      help: "Eye movement not accounted for by smooth compensation, in socket normalised units. This is the primary instability signal.",
      muted: !isPresent(gaze?.residual_rms_offset_units),
    },
    {
      label: "Same figure in degrees",
      value: isPresent(gaze?.residual_rms_deg_approx)
        ? degrees(gaze?.residual_rms_deg_approx, 2)
        : "n/a",
      help: "Converted using a fixed anatomical constant rather than a per person calibration, so treat it as an indicative magnitude only.",
      muted: true,
    },
    {
      label: "Largest single deviation",
      value: num(gaze?.residual_max_offset_units, 5),
      help: "Worst single frame departure from smooth compensation.",
      muted: !isPresent(gaze?.residual_max_offset_units),
    },
    {
      label: "Frames analysed",
      value: int(gaze?.moving_frames_analyzed),
      help: "Frames where the head moved fast enough to assess compensation. At least 10 are needed.",
    },
    {
      label: "Frames excluded as blinks",
      value: isPresent(gaze?.frames_excluded_blink)
        ? int(gaze?.frames_excluded_blink)
        : "Not assessed",
      help: isPresent(gaze?.frames_excluded_blink)
        ? "Blinks are removed before fitting, because closed eye landmarks produce spurious offsets."
        : "This session was captured before blink rejection existed, so blinks may be inflating the figures above.",
      muted: !isPresent(gaze?.frames_excluded_blink),
    },
  ]

  const headMetrics: Metric[] = [
    {
      label: "Mean sweep amplitude",
      value: degrees(head?.mean_sweep_amplitude_deg),
      help: "Average peak to peak rotation per sweep. The standardized protocol asks for 160 degrees, being 80 degrees each side.",
    },
    {
      label: "Total yaw range",
      value: degrees(head?.yaw_range_deg),
      help: "Full left to right excursion observed across the session.",
    },
    {
      label: "Mean sweep duration",
      value: seconds(head?.mean_sweep_duration_s, 2),
      help: "The protocol's 50 bpm metronome corresponds to 1.2 seconds per sweep.",
      muted: !isPresent(head?.mean_sweep_duration_s),
    },
    {
      label: "Pace consistency",
      value: num(head?.sweep_duration_cv, 3),
      help: "Variation in sweep duration within this session. Lower is steadier, and a drifting pace mixes different demands into one result.",
      muted: !isPresent(head?.sweep_duration_cv),
    },
    {
      label: "Peak rotation speed",
      value: isPresent(head?.max_peak_angular_velocity_dps)
        ? `${num(head?.max_peak_angular_velocity_dps, 1)} deg/s`
        : "n/a",
      help: "Fastest rotation reached. Faster rotation makes fixation harder, so this affects the gaze figures.",
    },
    {
      label: "Total sweeps",
      value: int(head?.total_sweeps),
      help: "A sweep is one traverse between rotation extremes, so one repetition is two sweeps.",
    },
    {
      label: "Off axis roll",
      value: degrees(head?.roll_range_deg),
      help: "Head tilt during what should be pure rotation. Large values suggest tilting rather than turning, though the pose maths also couples axes at large angles, so some of this may be estimation artifact.",
    },
    {
      label: "Off axis pitch",
      value: degrees(head?.pitch_range_deg),
      help: "Nodding during what should be pure rotation.",
    },
  ]

  const trackingMetrics: Metric[] = [
    {
      label: "Face detected",
      value: percent(tracking?.face_detection_rate, 1),
      help: "Share of frames where a face was found. Low values make everything else unreliable.",
    },
    {
      label: "Frames captured",
      value: isPresent(tracking?.total_frames)
        ? `${int(tracking?.frames_with_face)} of ${int(tracking?.total_frames)}`
        : "n/a",
    },
    {
      label: "Effective frame rate",
      value: isPresent(tracking?.effective_fps)
        ? `${num(tracking?.effective_fps, 1)} fps`
        : "n/a",
      help: "Achieved rate. Face landmark inference, not the camera, is normally the limit.",
    },
    {
      label: "Session duration",
      value: seconds(session.session?.duration_s, 1),
    },
  ]

  const failedGates = screening?.data_quality?.gates_failed ?? []
  const advisories = fidelity?.advisory_flags ?? []

  return (
    <DashboardShell
      title={recordedAt}
      backHref="/sessions"
      backLabel="Sessions"
    >
      <SectionHeader
        as="h1"
        title="Session results"
        description={`Recorded ${recordedAt}. ${statusLabel(screening?.status)}.`}
        actions={
          <DeleteSessionButton
            id={detail.id}
            label="Delete"
            capturedAt={recordedAt}
            redirectTo="/sessions"
          />
        }
      />

      {/* ---- hero ---- */}
      <Card className="overflow-hidden border-primary/25">
        <CardContent className="grid gap-8 py-6 @3xl/main:grid-cols-[minmax(0,320px)_1fr]">
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-[0.7rem] font-medium uppercase tracking-wider text-muted-foreground">
                Screening tier
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <TierBadge
                  tier={summary.severity_tier}
                  className="px-3 py-1 text-base"
                />
                {isPresent(screening?.composite_score) ? (
                  <span className="font-mono text-sm text-muted-foreground tabular-nums">
                    {num(screening?.composite_score, 2)} / 100
                  </span>
                ) : null}
              </div>
            </div>
            <TierMeter
              composite={screening?.composite_score}
              tier={summary.severity_tier}
              thresholds={screening?.method?.tier_thresholds}
            />
          </div>

          <div className="grid gap-6 sm:grid-cols-3">
            <KeyFact
              label="Self reported symptoms"
              value={
                isPresent(session.self_reported_symptoms?.score)
                  ? `${session.self_reported_symptoms?.score} / 10`
                  : "Not reported"
              }
              detail="Reported immediately after the test, where 0 is none and 10 is worst imaginable."
            />
            <KeyFact
              label="Camera signal"
              value={<ObjectiveSignalBadge usable={objectiveUsable} />}
              detail={
                objectiveUsable
                  ? "The gaze measurement passed its quality checks and contributed to the tier."
                  : "The gaze measurement failed its quality checks, so the tier rests on the symptom score alone."
              }
            />
            <KeyFact
              label="Repetitions"
              value={
                <span className="flex items-baseline gap-2">
                  <span className="font-mono tabular-nums">
                    {int(head?.completed_reps)}
                  </span>
                  <span className="text-sm font-normal text-muted-foreground">
                    of {int(session.session?.target_reps)}
                  </span>
                </span>
              }
              detail={
                <RepDots
                  completed={head?.completed_reps}
                  target={session.session?.target_reps}
                />
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 @3xl/main:grid-cols-2">
        <ScreeningDisclaimer
          text={screening?.disclaimer || disclaimers.screening}
        />
        <SessionDisclaimer text={session.disclaimer} />
      </div>

      {/* ---- notes ---- */}
      {screening?.notes?.length ? (
        <Section
          title="How this result was reached"
          description="Written by the scoring layer as it ran, not composed afterwards."
        >
          <ul className="space-y-2.5">
            {screening.notes.map((note) => (
              <li
                key={note}
                className="flex gap-3 rounded-lg border border-border/60 bg-muted/25 px-4 py-3 text-sm leading-relaxed"
              >
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {/* ---- quality ---- */}
      {failedGates.length > 0 || advisories.length > 0 ? (
        <Section
          title="Data quality"
          description="Checks that did not pass. Failed gates stop the camera signal being used. Protocol advisories do not, but they mean the figures are not comparable to published norms."
        >
          <div className="grid gap-3 @3xl/main:grid-cols-2">
            {failedGates.length > 0 ? (
              <Card className="border-rose-300/70 bg-rose-50/50 dark:border-rose-900/60 dark:bg-rose-950/20">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Failed quality gates</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-1.5">
                  {failedGates.map((gate) => (
                    <Badge
                      key={gate}
                      variant="outline"
                      className="border-rose-300 bg-rose-100/70 text-rose-900 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200"
                    >
                      {humanizeFlag(gate)}
                    </Badge>
                  ))}
                </CardContent>
              </Card>
            ) : null}
            {advisories.length > 0 ? (
              <Card className="border-amber-300/70 bg-amber-50/50 dark:border-amber-900/60 dark:bg-amber-950/20">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Protocol advisories</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-1.5">
                  {advisories.map((flag) => (
                    <Badge
                      key={flag}
                      variant="outline"
                      className="border-amber-300 bg-amber-100/70 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
                    >
                      {humanizeFlag(flag)}
                    </Badge>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </div>
        </Section>
      ) : null}

      {/* ---- metrics ---- */}
      <Section
        title="Measurements"
        description="Everything the tracker recorded, with what each figure means."
      >
        <div className="grid gap-4 @4xl/main:grid-cols-2">
          <MetricCard
            accent
            title="Gaze stability"
            description={
              gaze?.insufficient_data === true
                ? "Not enough usable data to assess gaze stability for this session."
                : "How well the eyes held the target while the head rotated. This is the core measurement the test exists to capture."
            }
            metrics={gazeMetrics}
          />
          <MetricCard
            title="Head motion"
            description="What the head actually did, which determines whether the gaze figures describe the intended movement."
            metrics={headMetrics}
          />
          <MetricCard
            title="Tracking quality"
            description="Whether the camera captured enough to trust anything else on this page."
            metrics={trackingMetrics}
          />
          {fidelity?.reference ? (
            <MetricCard
              title="Protocol comparison"
              description={fidelity.reference.description}
              metrics={[
                {
                  label: "Amplitude against protocol",
                  value: isPresent(fidelity.amplitude_ratio)
                    ? `${(fidelity.amplitude_ratio * 100).toFixed(0)}%`
                    : "n/a",
                  help: `Observed ${degrees(
                    fidelity.observed?.mean_sweep_amplitude_deg
                  )} against a reference of ${degrees(
                    fidelity.reference.sweep_amplitude_deg
                  )}.`,
                },
                {
                  label: "Pace against protocol",
                  value: isPresent(fidelity.pace_ratio)
                    ? `${(fidelity.pace_ratio * 100).toFixed(0)}%`
                    : "n/a",
                  help: `Observed ${num(
                    fidelity.observed?.effective_cadence_bpm,
                    1
                  )} bpm against a reference of ${num(
                    fidelity.reference.cadence_bpm,
                    0
                  )} bpm.`,
                },
                {
                  label: "Reference repetitions",
                  value: int(fidelity.reference.reps),
                },
                {
                  label: "Pace source",
                  value: fidelity.observed?.pace_derived_from_sweeps
                    ? "Derived from sweeps"
                    : "Recorded directly",
                  help: fidelity.observed?.pace_derived_from_sweeps
                    ? "This session predates the aggregate pace field, so pace was recomputed from the individual sweeps."
                    : undefined,
                  muted: fidelity.observed?.pace_derived_from_sweeps,
                },
              ]}
            />
          ) : null}
        </div>
      </Section>

      {/* ---- exercises ---- */}
      <ExerciseList
        recommendations={session.recommended_exercises}
        disclaimers={disclaimers}
      />

      {/* ---- method ---- */}
      {screening?.method ? (
        <details className="group rounded-xl border bg-muted/20 px-5 py-4">
          <summary className="cursor-pointer font-heading text-base font-semibold">
            How the tier is computed
          </summary>
          <div className="mt-4 space-y-3 text-sm">
            <p className="text-muted-foreground">
              Shown so the result can be audited rather than taken on trust.
            </p>
            {screening.method.composite_formula ? (
              <pre className="overflow-x-auto rounded-lg border bg-card p-3 text-xs">
                <code>{screening.method.composite_formula}</code>
              </pre>
            ) : null}
            {screening.method.tier_thresholds ? (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(screening.method.tier_thresholds)
                  .sort((a, b) => a[1] - b[1])
                  .map(([tier, threshold]) => (
                    <Badge key={tier} variant="secondary" className="capitalize">
                      {tier} at {threshold} and above
                    </Badge>
                  ))}
              </div>
            ) : null}
            {screening.method.symptom_floor_rule ? (
              <p className="text-muted-foreground">
                {screening.method.symptom_floor_rule}
              </p>
            ) : null}
            {screening.method.calibration_status ? (
              <p className="leading-relaxed text-muted-foreground">
                {screening.method.calibration_status}
              </p>
            ) : null}
            {screening.method.references?.length ? (
              <ul className="space-y-1 text-xs text-muted-foreground">
                {screening.method.references.map((reference) => (
                  <li key={reference}>{reference}</li>
                ))}
              </ul>
            ) : null}
            <p className="text-xs text-muted-foreground">
              Scoring schema {detail.scoring_schema_version ?? "unknown"}.{" "}
              {detail.scoring_source === "computed"
                ? "Scored on read, because no stored score exists for this capture."
                : "Read from the stored scored file."}
            </p>
          </div>
        </details>
      ) : null}
    </DashboardShell>
  )
}
