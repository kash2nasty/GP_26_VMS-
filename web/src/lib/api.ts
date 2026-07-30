/**
 * Typed access to the FastAPI backend in ../api.
 *
 * All of this runs in Server Components, so the browser never talks to the
 * Python API directly and the base URL stays server-side.
 *
 * Every field here is optional-by-default on purpose. The session files on disk
 * were written by several versions of the Python scoring layer: older ones have
 * no `protocol_fidelity`, no `frames_excluded_blink`, and a `gaze_stability`
 * block whose values can all be null. Modelling those as required would let a
 * genuinely older-but-valid session crash the page.
 */

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000"

export type SeverityTier = "minimal" | "mild" | "moderate" | "pronounced"

/** Mirrors scoring/indications.py. */
export type Finding = "indicated" | "not_indicated" | "not_assessable"
export type Strength = "borderline" | "present" | "marked"
export type Urgency = "routine" | "prompt" | "emergency_if_new"
export type EvidenceBasis =
  | "published_sign_provisional_threshold"
  | "bespoke_metric_arbitrary_threshold"

export type Indication = {
  id: string
  label: string
  /** Condition families this pattern is associated with. Never asserted. */
  screens_for: string[]
  /** True for the check that restates the subtest itself, i.e. the severity tier. */
  is_primary?: boolean
  finding: Finding
  strength?: Strength | null
  /** The numbers the decision was made from. Values may be numbers or strings. */
  measured?: Record<string, number | string | null>
  thresholds?: Record<string, number | string | number[] | null>
  interpretation?: string
  /** Only set when the finding is not_assessable. */
  reason?: string | null
  urgency: Urgency
  evidence_basis: EvidenceBasis
  caveat?: string | null
  next_step?: string | null
  references?: string[]
}

export type IndicationPanel = {
  schema_version?: string
  panel: Indication[]
  checks_run?: number
  indicated: string[]
  /** Flagged checks other than the subtest itself, which the tier already reports. */
  secondary_indicated?: string[]
  secondary_checks_run?: number
  not_assessable: string[]
  highest_urgency?: Urgency | null
  summary?: string
  tracking_sufficient?: boolean
  disclaimer?: string
  emergency_note?: string
  method?: {
    what_an_indication_means?: string
    what_not_indicated_means?: string
    evidence_basis_values?: Record<string, string>
    shared_gates?: Record<string, number>
  }
}

export type Disclaimers = {
  screening: string
  exercises: string
  safety_note: string
}

export type SessionSummary = {
  id: string
  captured_at: string | null
  duration_s?: number | null
  symptom_score?: number | null
  symptom_provided: boolean
  severity_tier?: SeverityTier | null
  composite_score?: number | null
  status?: string | null
  objective_signal_usable?: boolean | null
  gates_failed: string[]
  completed_reps?: number | null
  face_detection_rate?: number | null
  /**
   * null means the session predates protocol-fidelity assessment entirely,
   * which is NOT the same as failing it. The UI must render those differently.
   */
  comparable_to_clinical_protocol?: boolean | null
  scoring_source: "file" | "computed"
  scoring_schema_version?: string | null
  /** Ids of the indications that crossed their threshold. */
  indications_indicated?: string[]
  indications_not_assessable?: number
  indications_checks_run?: number | null
  indications_highest_urgency?: Urgency | null
  indications_source?: "file" | "computed"
}

export type UnreadableSession = { id: string; error: string }

export type SessionListResponse = {
  sessions: SessionSummary[]
  unreadable: UnreadableSession[]
  disclaimers: Disclaimers
}

export type GazeStability = {
  moving_frames_analyzed?: number | null
  compensation_slope?: number | null
  compensation_r2?: number | null
  residual_rms_offset_units?: number | null
  residual_rms_deg_approx?: number | null
  residual_max_offset_units?: number | null
  iris_std_during_motion_offset_units?: number | null
  fixation_stability_score?: number | null
  insufficient_data?: boolean
  frames_excluded_blink?: number | null
  min_eye_aperture_ratio?: number | null
  metric_notes?: string
}

export type HeadMotion = {
  insufficient_data?: boolean
  completed_reps?: number | null
  total_sweeps?: number | null
  reached_target_reps?: boolean | null
  yaw_range_deg?: number | null
  mean_sweep_amplitude_deg?: number | null
  max_sweep_amplitude_deg?: number | null
  mean_peak_angular_velocity_dps?: number | null
  max_peak_angular_velocity_dps?: number | null
  mean_sweep_duration_s?: number | null
  sweep_duration_cv?: number | null
  pitch_range_deg?: number | null
  roll_range_deg?: number | null
}

export type ProtocolFidelity = {
  reference?: {
    sweep_amplitude_deg?: number
    sweep_duration_s?: number
    cadence_bpm?: number
    reps?: number
    description?: string
    sources?: string[]
  }
  observed?: {
    mean_sweep_amplitude_deg?: number | null
    mean_sweep_duration_s?: number | null
    effective_cadence_bpm?: number | null
    sweep_duration_cv?: number | null
    completed_reps?: number | null
    roll_range_deg?: number | null
    pitch_range_deg?: number | null
    pace_derived_from_sweeps?: boolean
  }
  amplitude_ratio?: number | null
  pace_ratio?: number | null
  advisory_flags?: string[]
  comparable_to_clinical_protocol?: boolean
  enforced_as_gates?: boolean
}

export type ScreeningSummary = {
  scoring_schema_version?: string
  status?: string
  severity_tier?: SeverityTier | null
  composite_score?: number | null
  components?: {
    symptom_component?: number | null
    instability_component?: number | null
    symptom_weight?: number
    instability_weight?: number
  }
  data_quality?: {
    face_detection_rate?: number | null
    compensation_r2?: number | null
    fixation_stability_score?: number | null
    completed_reps?: number | null
    frames_excluded_blink?: number | null
    objective_signal_usable?: boolean
    gates_failed?: string[]
    protocol_advisory_flags?: string[]
  }
  protocol_fidelity?: ProtocolFidelity
  method?: {
    composite_formula?: string
    tier_thresholds?: Record<string, number>
    symptom_floor_rule?: string
    calibration_status?: string
    references?: string[]
  }
  notes?: string[]
  disclaimer?: string
}

export type Exercise = {
  id: string
  name: string
  protocol_stage?: string
  description?: string
  suggested_frequency?: string
  rationale?: string
}

export type RecommendedExercises = {
  protocol?: string
  severity_tier?: SeverityTier | null
  summary?: string
  progression?: string | null
  exercises: Exercise[]
  typical_course?: string | null
  safety_note?: string
  protocol_references?: string[]
  disclaimer?: string
}

/**
 * The measurement blocks added in session schema 0.2.0.
 *
 * Every field is optional because every session file already on disk was written
 * before these existed. The UI must render "never measured" differently from
 * "measured as zero", which is why nothing here has a default.
 */
export type OculomotorSignals = {
  insufficient_data?: boolean
  frames_analyzed?: number | null
  blink_count?: number | null
  blink_rate_per_min?: number | null
  mean_blink_duration_s?: number | null
  fixation_break_count?: number | null
  fixation_break_rate_per_s?: number | null
  largest_fixation_break_offset_units?: number | null
  oscillation_frequency_hz?: number | null
  oscillation_rhythmicity?: number | null
  oscillation_amplitude_offset_units?: number | null
  sample_rate_hz?: number | null
  oscillation_band_hz?: number[]
  metric_notes?: string
}

export type OcularAlignment = {
  insufficient_data?: boolean
  frames_analyzed?: number | null
  horizontal_disparity_mean_offset_units?: number | null
  horizontal_disparity_std_offset_units?: number | null
  vertical_disparity_mean_offset_units?: number | null
  vertical_disparity_std_offset_units?: number | null
  vertical_disparity_max_offset_units?: number | null
  metric_notes?: string
}

export type EyelidSignals = {
  insufficient_data?: boolean
  frames_analyzed?: number | null
  left_aperture_median?: number | null
  right_aperture_median?: number | null
  aperture_asymmetry_ratio?: number | null
  aperture_relative_decline?: number | null
  aperture_trend_per_min?: number | null
  fatigue_window_s?: number | null
  metric_notes?: string
}

export type HeadControl = {
  insufficient_data?: boolean
  leftward_residual_rms_offset_units?: number | null
  rightward_residual_rms_offset_units?: number | null
  direction_asymmetry_index?: number | null
  leftward_sweeps?: number | null
  rightward_sweeps?: number | null
  leftward_mean_peak_velocity_dps?: number | null
  rightward_mean_peak_velocity_dps?: number | null
  velocity_asymmetry_index?: number | null
  tremor_frequency_hz?: number | null
  tremor_rhythmicity?: number | null
  tremor_amplitude_deg?: number | null
  sample_rate_hz?: number | null
  tremor_band_hz?: number[]
  off_axis_coupling_ratio?: number | null
  metric_notes?: string
}

export type FacialSymmetry = {
  insufficient_data?: boolean
  frames_analyzed?: number | null
  mouth_corner_asymmetry?: number | null
  brow_height_asymmetry?: number | null
  mouth_corner_asymmetry_spread?: number | null
  metric_notes?: string
}

export type SessionDetail = {
  id: string
  captured_at: string | null
  scoring_source: "file" | "computed"
  scoring_schema_version?: string | null
  /** "computed" when the panel was built on read because the file predates it. */
  indications_source?: "file" | "computed"
  summary: SessionSummary
  session: {
    schema_version?: string
    test_type?: string
    disclaimer?: string
    session?: {
      started_at_unix?: number
      ended_at_unix?: number
      duration_s?: number
      target_reps?: number
    }
    tracking_quality?: {
      total_frames?: number
      frames_with_face?: number
      face_detection_rate?: number | null
      mean_landmark_confidence?: number | null
      effective_fps?: number | null
    }
    self_reported_symptoms?: {
      scale?: string
      prompt?: string
      score?: number | null
      provided?: boolean
    }
    head_motion?: HeadMotion
    gaze_stability?: GazeStability
    oculomotor_signals?: OculomotorSignals
    ocular_alignment?: OcularAlignment
    eyelid_signals?: EyelidSignals
    head_control?: HeadControl
    facial_symmetry?: FacialSymmetry
    screening_summary?: ScreeningSummary
    screening_indications?: IndicationPanel
    recommended_exercises?: RecommendedExercises
  }
  disclaimers: Disclaimers
}

/** Thrown when the API is unreachable, so pages can show a real explanation. */
export class ApiUnreachableError extends Error {
  constructor(public readonly url: string, cause: unknown) {
    super(
      `Could not reach the screening API at ${url}. Start it with: ` +
        `uvicorn api.main:app --reload --port 8000`
    )
    this.name = "ApiUnreachableError"
    this.cause = cause
  }
}

async function getJson<T>(path: string): Promise<T | null> {
  const url = `${API_BASE_URL}${path}`
  let response: Response
  try {
    // no-store because sessions/ changes whenever a capture is run; a cached
    // list would quietly hide new sessions.
    response = await fetch(url, { cache: "no-store" })
  } catch (cause) {
    throw new ApiUnreachableError(url, cause)
  }

  if (response.status === 404) return null
  if (!response.ok) {
    throw new Error(`${url} responded ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

export async function fetchSessions(): Promise<SessionListResponse> {
  const body = await getJson<SessionListResponse>("/sessions")
  // /sessions has no 404 path, but keep the types honest rather than asserting.
  return body ?? { sessions: [], unreadable: [], disclaimers: emptyDisclaimers() }
}

export async function fetchSession(id: string): Promise<SessionDetail | null> {
  return getJson<SessionDetail>(`/sessions/${encodeURIComponent(id)}`)
}

function emptyDisclaimers(): Disclaimers {
  return { screening: "", exercises: "", safety_note: "" }
}
