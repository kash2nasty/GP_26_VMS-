import { notFound } from "next/navigation"

import { ApiError } from "@/components/api-error"
import { DashboardShell, Section, SectionHeader } from "@/components/dashboard-shell"
import { DeleteSessionButton } from "@/components/delete-session-button"
import { ScreeningDisclaimer, SessionDisclaimer } from "@/components/disclaimer"
import { ExerciseList } from "@/components/exercise-list"
import { IndicationList, IndicationSummary } from "@/components/indication-panel"
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
 * `params` is a Promise in Next.js 16: synchronous access was fully removed in this
 * major version, so it must be awaited.
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
  const panel = session.screening_indications
  const gaze = session.gaze_stability
  const head = session.head_motion
  const tracking = session.tracking_quality
  const fidelity = screening?.protocol_fidelity
  const objectiveUsable = screening?.data_quality?.objective_signal_usable
  const recordedAt = formatDateTime(detail.captured_at)

  // The wider signal set, added in session schema 0.2.0. Absent on every capture
  // made before it existed, which the cards below have to render as "never
  // measured" rather than as zeros.
  const oculomotor = session.oculomotor_signals
  const alignment = session.ocular_alignment
  const eyelid = session.eyelid_signals
  const control = session.head_control
  const facial = session.facial_symmetry
  const hasWiderSignals = Boolean(
    oculomotor || alignment || eyelid || control || facial
  )

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
      label: "Sampling rate from timestamps",
      value: isPresent(oculomotor?.sample_rate_hz)
        ? `${num(oculomotor?.sample_rate_hz, 1)} Hz`
        : "Not recorded",
      help: "How densely the movement was actually sampled. This is the figure that decides whether nystagmus or tremor can be measured at all: nothing above half of it is visible.",
      muted: !isPresent(oculomotor?.sample_rate_hz),
    },
    {
      label: "Session duration",
      value: seconds(session.session?.duration_s, 1),
    },
  ]

  const directionMetrics: Metric[] = [
    {
      label: "Direction asymmetry index",
      value: num(control?.direction_asymmetry_index, 3),
      help: "Difference between the two turning directions over their sum. 0 means gaze behaved identically each way; a large value is the pattern a one-sided vestibular loss produces and is invisible to any whole-session average.",
      muted: !isPresent(control?.direction_asymmetry_index),
    },
    {
      label: "Instability turning one way",
      value: num(control?.leftward_residual_rms_offset_units, 5),
      help: "Unexplained eye motion during sweeps toward positive yaw.",
      muted: !isPresent(control?.leftward_residual_rms_offset_units),
    },
    {
      label: "Instability turning the other",
      value: num(control?.rightward_residual_rms_offset_units, 5),
      help: "The same figure for sweeps toward negative yaw. Comparing the two is the whole point of this card.",
      muted: !isPresent(control?.rightward_residual_rms_offset_units),
    },
    {
      label: "Speed asymmetry index",
      value: num(control?.velocity_asymmetry_index, 3),
      help: "Whether the two directions were performed at similar speeds. If this is high, any gaze difference above may be a consequence of technique rather than of vestibular function.",
      muted: !isPresent(control?.velocity_asymmetry_index),
    },
    {
      label: "Sweeps each way",
      value:
        isPresent(control?.leftward_sweeps) && isPresent(control?.rightward_sweeps)
          ? `${int(control?.leftward_sweeps)} and ${int(control?.rightward_sweeps)}`
          : "n/a",
      help: "At least two in each direction are needed before the comparison means anything.",
    },
    {
      label: "Off axis coupling",
      value: num(control?.off_axis_coupling_ratio, 3),
      help: "Roll plus pitch range over yaw range. The subtest asks for pure rotation, so a high value means the head tilted or nodded instead of turning.",
      muted: !isPresent(control?.off_axis_coupling_ratio),
    },
    {
      label: "Head oscillation",
      value: isPresent(control?.tremor_frequency_hz)
        ? `${num(control?.tremor_frequency_hz, 1)} Hz`
        : "None found",
      help: `Strongest rhythmic component riding on the sweeps, searched between ${
        control?.tremor_band_hz?.join(" and ") ?? "2.5 and 6"
      } Hz. The upper bound is set by the frame rate, not by physiology.`,
      muted: !isPresent(control?.tremor_frequency_hz),
    },
    {
      label: "Its amplitude",
      value: degrees(control?.tremor_amplitude_deg, 2),
      help: "Peak to peak size of that oscillation, measured from the peak frequency band alone so the intended sweep does not contribute to it.",
      muted: !isPresent(control?.tremor_amplitude_deg),
    },
  ]

  const oculomotorMetrics: Metric[] = [
    {
      label: "Blink rate",
      value: isPresent(oculomotor?.blink_rate_per_min)
        ? `${num(oculomotor?.blink_rate_per_min, 1)} / min`
        : "Not recorded",
      help: "Blink events, not blink frames. Measured during a demanding visual task, which lowers the rate, so resting norms do not transfer directly.",
      muted: !isPresent(oculomotor?.blink_rate_per_min),
    },
    {
      label: "Blinks counted",
      value: int(oculomotor?.blink_count),
      muted: !isPresent(oculomotor?.blink_count),
    },
    {
      label: "Mean blink duration",
      value: seconds(oculomotor?.mean_blink_duration_s, 3),
      muted: !isPresent(oculomotor?.mean_blink_duration_s),
    },
    {
      label: "Fixation breaks",
      value: isPresent(oculomotor?.fixation_break_rate_per_s)
        ? `${num(oculomotor?.fixation_break_rate_per_s, 2)} / s`
        : "n/a",
      help: "How often gaze left the smoothly compensating path. Repeated jumps back onto the target rather than continuous tracking is the pattern called saccadic intrusion.",
      muted: !isPresent(oculomotor?.fixation_break_rate_per_s),
    },
    {
      label: "Largest break",
      value: num(oculomotor?.largest_fixation_break_offset_units, 5),
      muted: !isPresent(oculomotor?.largest_fixation_break_offset_units),
    },
    {
      label: "Eye oscillation",
      value: isPresent(oculomotor?.oscillation_frequency_hz)
        ? `${num(oculomotor?.oscillation_frequency_hz, 1)} Hz`
        : "None found",
      help: `Strongest periodic component of the unexplained eye motion, searched between ${
        oculomotor?.oscillation_band_hz?.join(" and ") ?? "1 and 5"
      } Hz. Rhythmic involuntary eye movement is what the word nystagmus describes.`,
      muted: !isPresent(oculomotor?.oscillation_frequency_hz),
    },
    {
      label: "How rhythmic it was",
      value: num(oculomotor?.oscillation_rhythmicity, 3),
      help: "Share of in-band power sitting in that peak. Near 1 is a clean oscillation; a low value means there was no real periodicity to find.",
      muted: !isPresent(oculomotor?.oscillation_rhythmicity),
    },
  ]

  const eyeStructureMetrics: Metric[] = [
    {
      label: "Horizontal alignment difference",
      value: num(alignment?.horizontal_disparity_mean_offset_units, 5),
      help: "Right iris offset minus left, averaged. An uncalibrated constant bias from the landmark model is inside this number, so only large values mean anything.",
      muted: !isPresent(alignment?.horizontal_disparity_mean_offset_units),
    },
    {
      label: "Vertical alignment difference",
      value: num(alignment?.vertical_disparity_mean_offset_units, 5),
      help: "The more clinically interesting of the two: vertical misalignment is associated with central rather than refractive causes.",
      muted: !isPresent(alignment?.vertical_disparity_mean_offset_units),
    },
    {
      label: "Steadiness of alignment",
      value: num(alignment?.horizontal_disparity_std_offset_units, 5),
      help: "Variability of the horizontal difference. Unlike the mean, this is free of the constant landmark bias.",
      muted: !isPresent(alignment?.horizontal_disparity_std_offset_units),
    },
    {
      label: "Eyelid opening, one eye",
      value: num(eyelid?.left_aperture_median, 3),
      help: "Median vertical opening over eye width, across open-eye frames only.",
      muted: !isPresent(eyelid?.left_aperture_median),
    },
    {
      label: "Eyelid opening, the other",
      value: num(eyelid?.right_aperture_median, 3),
      muted: !isPresent(eyelid?.right_aperture_median),
    },
    {
      label: "Eyelid asymmetry",
      value: percent(eyelid?.aperture_asymmetry_ratio, 1),
      help: "Difference between the two eyes over their mean. Side labels follow the landmark groups and have not been verified against the subject's anatomical sides.",
      muted: !isPresent(eyelid?.aperture_asymmetry_ratio),
    },
    {
      label: "Opening lost over the session",
      value: percent(eyelid?.aperture_relative_decline, 1),
      help: "First third against last third. A droop that appears only with sustained effort is a different observation from one that is simply present.",
      muted: !isPresent(eyelid?.aperture_relative_decline),
    },
    {
      label: "Resting facial asymmetry",
      value: num(facial?.mouth_corner_asymmetry, 4),
      help: `Height difference between the mouth corners in face-width units, over ${int(
        facial?.frames_analyzed
      )} near-frontal frames. A test built out of turning the head can contain very few of those.`,
      muted: !isPresent(facial?.mouth_corner_asymmetry),
    },
  ]

  const failedGates = screening?.data_quality?.gates_failed ?? []
  const advisories = fidelity?.advisory_flags ?? []

  return (
    <DashboardShell title={recordedAt} backHref="/sessions" backLabel="Sessions">
      <SectionHeader
        as="h1"
        eyebrow={`Recorded ${recordedAt}`}
        title="Session results"
        description={statusLabel(screening?.status)}
        actions={
          <DeleteSessionButton
            id={detail.id}
            label="Delete"
            variant="outline"
            capturedAt={recordedAt}
            redirectTo="/sessions"
          />
        }
      />

      {/* ---- hero ---- */}
      <Card className="hero-wash ring-primary/25">
        <CardContent className="grid gap-7 @3xl/main:grid-cols-[minmax(0,300px)_1fr]">
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="eyebrow">Screening tier</p>
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

          <div className="grid gap-6 sm:grid-cols-2 @3xl/main:grid-cols-4">
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
              label="Protocol"
              value={
                <ProtocolBadge
                  comparable={fidelity?.comparable_to_clinical_protocol}
                />
              }
              detail={
                fidelity?.comparable_to_clinical_protocol === false
                  ? "This session deviated from the standardized protocol, so the figures are not comparable to published norms."
                  : "Whether this capture can be read against published norms."
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

      {/* ---- indications ---- */}
      {panel ? (
        <Section
          eyebrow="Beyond the subtest"
          title="Screening indications"
          description={
            detail.indications_source === "computed"
              ? "This panel was computed when the page loaded, because the stored score for this session predates it. The numbers behind it come from the capture itself and are unchanged."
              : `${
                  (panel.secondary_checks_run ?? panel.panel.length - 1)
                } further checks run over the same capture, alongside the subtest itself. Each names a measurement, the threshold it was compared against, and the conditions that pattern is associated with. None of them is a diagnosis.`
          }
        >
          <div className="space-y-4">
            <IndicationSummary panel={panel} />
            <IndicationList panel={panel} />
          </div>
        </Section>
      ) : null}

      <div className="grid gap-3 @3xl/main:grid-cols-2">
        <ScreeningDisclaimer
          text={panel?.disclaimer || screening?.disclaimer || disclaimers.screening}
        />
        <SessionDisclaimer text={session.disclaimer} />
      </div>

      {/* ---- notes ---- */}
      {screening?.notes?.length ? (
        <Section
          title="How the tier was reached"
          description="Written by the scoring layer as it ran, not composed afterwards."
        >
          <ul className="space-y-2">
            {screening.notes.map((note) => (
              <li
                key={note}
                className="inset-panel flex gap-3 px-4 py-3 text-sm leading-relaxed"
              >
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                <span className="max-w-[80ch]">{note}</span>
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
              <Card
                size="sm"
                className="bg-rose-50/50 ring-rose-300/70 dark:bg-rose-950/20 dark:ring-rose-900/60"
              >
                <CardHeader>
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
              <Card
                size="sm"
                className="bg-amber-50/50 ring-amber-300/70 dark:bg-amber-950/20 dark:ring-amber-900/60"
              >
                <CardHeader>
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
        description="Everything the tracker recorded, with what each figure means. These are the numbers the indications above were derived from."
      >
        <div className="grid gap-3 @4xl/main:grid-cols-2">
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
          {hasWiderSignals ? (
            <>
              <MetricCard
                title="Direction and head control"
                description="The same gaze residual split by which way the head was turning, plus any rhythmic oscillation riding on the sweeps."
                metrics={directionMetrics}
              />
              <MetricCard
                title="Blinking and fixation"
                description="Eyelid events and the shape of the unexplained eye motion over time."
                metrics={oculomotorMetrics}
              />
              <MetricCard
                title="Eye alignment, eyelids and face"
                description="Measurements that describe the person rather than the movement. All are uncalibrated and none separates a long-standing difference from a new one."
                metrics={eyeStructureMetrics}
              />
            </>
          ) : null}
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
        <details className="group inset-panel px-5 py-4">
          <summary className="cursor-pointer font-heading text-base font-semibold">
            How the tier is computed
          </summary>
          <div className="mt-4 space-y-3 text-sm">
            <p className="max-w-[70ch] text-muted-foreground">
              Shown so the result can be audited rather than taken on trust.
            </p>
            {screening.method.composite_formula ? (
              <pre className="overflow-x-auto rounded-lg bg-card p-3 text-xs ring-1 ring-foreground/10">
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
              <p className="max-w-[70ch] text-muted-foreground">
                {screening.method.symptom_floor_rule}
              </p>
            ) : null}
            {screening.method.calibration_status ? (
              <p className="max-w-[70ch] leading-relaxed text-muted-foreground">
                {screening.method.calibration_status}
              </p>
            ) : null}
            {panel?.method?.what_not_indicated_means ? (
              <p className="max-w-[70ch] leading-relaxed text-muted-foreground">
                On the indications panel: {panel.method.what_not_indicated_means}
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
