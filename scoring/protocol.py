"""Protocol fidelity: how closely a session matched the standardized VOMS test.

WHY THIS EXISTS
    The gaze-instability metric is computed over whatever head motion actually
    happened. It says nothing about whether that motion resembled the test the
    metric is meant to characterise. Two sessions from the same person at
    different rotation speeds produce very different residuals, so a tier derived
    without checking fidelity is not comparable across sessions -- or to anything
    published.

THE REFERENCE PROTOCOL
    Standardized VOMS visual motion sensitivity: standing, feet shoulder width
    apart, arm outstretched with gaze fixed on the thumb; head, eyes and trunk
    rotate together through 80 degrees to each side, paced by a metronome at
    50 bpm with one beat per direction; 5 repetitions.

    That gives a reference sweep (one extreme to the other) of 160 degrees
    traversed in 60/50 = 1.2 s -- a mean angular velocity near 133 deg/s.

WHY DEVIATIONS ARE ADVISORY, NOT HARD GATES
    A single front-facing webcam may not be able to track +/-80 degrees of yaw at
    all: the face approaches profile and the landmarker degrades. Until that
    ceiling is measured (see check_yaw_ceiling.py), hard-gating on protocol
    amplitude would mark every session unusable and discard the objective signal
    entirely. So amplitude and pace deviations are reported as advisory flags and
    surfaced in the summary notes, while `comparable_to_clinical_protocol` states
    plainly whether the session can be read against published norms.

    Set ENFORCE_AS_GATES = True to promote them to blocking gates once the
    reachable amplitude is known.
"""
from __future__ import annotations

PROTOCOL_SWEEP_AMPLITUDE_DEG = 160.0   # 80 deg each side, one extreme to the other
PROTOCOL_CADENCE_BPM = 50.0            # one beat per direction
PROTOCOL_SWEEP_DURATION_S = 60.0 / PROTOCOL_CADENCE_BPM   # 1.2 s
PROTOCOL_REPS = 5

PROTOCOL_REFERENCE_NOTE = (
    "Standing, arm outstretched with gaze fixed on the thumb; head, eyes and "
    "trunk rotate together 80 degrees to each side at 50 bpm (one beat per "
    "direction), 5 repetitions."
)

PROTOCOL_SOURCES = [
    "Mucha A, et al. A Brief Vestibular/Ocular Motor Screening (VOMS) Assessment "
    "to Evaluate Concussions. Am J Sports Med. 2014;42(10):2479-2486.",
    "Physiopedia. Vestibular Oculomotor Motor Screening (VOMS) Assessment. "
    "https://www.physio-pedia.com/"
    "Vestibular_Oculomotor_Motor_Screening_(VOMS)_Assessment",
]

# Tolerances, all provisional. Ratios are observed / protocol.
AMPLITUDE_RATIO_RANGE = (0.75, 1.25)
PACE_RATIO_RANGE = (0.66, 1.5)

# Within-session pace steadiness. A pace that drifts through the session varies
# the demand on gaze stabilisation, so the residual mixes speeds together.
MAX_SWEEP_DURATION_CV = 0.35

# Off-axis motion. The test is a yaw rotation; large roll or pitch excursions mean
# the head tilted or nodded instead of rotating cleanly, which contaminates the
# yaw-vs-iris fit.
#
# Caveat kept in the open: the Euler decomposition in face_tracker couples axes at
# large yaw, so part of a high roll range may be decomposition artifact rather
# than genuine head tilt. That is another reason these are advisory.
MAX_ROLL_RANGE_DEG = 30.0
MAX_PITCH_RANGE_DEG = 25.0

# Flip to True to make amplitude/pace/off-axis deviations block the objective
# signal instead of merely flagging it.
ENFORCE_AS_GATES = False


def _number(block, key):
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _duration_stats_from_sweeps(head):
    """Recover mean sweep duration and its CV from the per-sweep list.

    Sessions captured before mean_sweep_duration_s existed still carry sweeps[],
    each with a duration_s. Deriving from those lets an old capture be re-scored
    with a real pace figure instead of "unknown" -- which matters because
    re-scoring old captures is the whole reason score_session.py is standalone.
    """
    sweeps = head.get("sweeps")
    if not isinstance(sweeps, list) or not sweeps:
        return None, None

    durations = []
    for sweep in sweeps:
        value = _number(sweep, "duration_s")
        if value is not None and value > 0:
            durations.append(value)
    if not durations:
        return None, None

    mean = sum(durations) / len(durations)
    if mean <= 1e-9:
        return None, None
    variance = sum((d - mean) ** 2 for d in durations) / len(durations)
    return round(mean, 3), round(variance ** 0.5 / mean, 4)


def _ratio(observed, reference):
    if observed is None or reference in (None, 0):
        return None
    return round(observed / reference, 4)


def assess(session: dict) -> dict:
    """Compare a session's head motion against the standardized protocol."""
    head = session.get("head_motion") or {}

    amplitude = _number(head, "mean_sweep_amplitude_deg")
    duration = _number(head, "mean_sweep_duration_s")
    duration_cv = _number(head, "sweep_duration_cv")
    reps = _number(head, "completed_reps")

    # Fall back to the per-sweep list for sessions captured before the aggregate
    # pace fields existed.
    pace_derived = False
    if duration is None:
        derived_duration, derived_cv = _duration_stats_from_sweeps(head)
        if derived_duration is not None:
            duration, pace_derived = derived_duration, True
            if duration_cv is None:
                duration_cv = derived_cv
    roll = _number(head, "roll_range_deg")
    pitch = _number(head, "pitch_range_deg")

    amplitude_ratio = _ratio(amplitude, PROTOCOL_SWEEP_AMPLITUDE_DEG)
    # Inverted deliberately: a LONGER sweep is a SLOWER pace, so pace_ratio < 1
    # consistently means "slower than protocol" for both directions of error.
    pace_ratio = _ratio(PROTOCOL_SWEEP_DURATION_S, duration)
    cadence_bpm = round(60.0 / duration, 2) if duration and duration > 0 else None

    flags = []
    if amplitude_ratio is None:
        flags.append("amplitude_unknown")
    elif not AMPLITUDE_RATIO_RANGE[0] <= amplitude_ratio <= AMPLITUDE_RATIO_RANGE[1]:
        flags.append(
            "amplitude_below_protocol" if amplitude_ratio < AMPLITUDE_RATIO_RANGE[0]
            else "amplitude_above_protocol"
        )

    if pace_ratio is None:
        flags.append("pace_unknown")
    elif not PACE_RATIO_RANGE[0] <= pace_ratio <= PACE_RATIO_RANGE[1]:
        flags.append(
            "pace_slower_than_protocol" if pace_ratio < PACE_RATIO_RANGE[0]
            else "pace_faster_than_protocol"
        )

    if duration_cv is not None and duration_cv > MAX_SWEEP_DURATION_CV:
        flags.append("pace_inconsistent_within_session")

    if roll is not None and roll > MAX_ROLL_RANGE_DEG:
        flags.append("excessive_roll")
    if pitch is not None and pitch > MAX_PITCH_RANGE_DEG:
        flags.append("excessive_pitch")

    if reps is not None and reps < PROTOCOL_REPS:
        flags.append("fewer_reps_than_protocol")

    return {
        "reference": {
            "sweep_amplitude_deg": PROTOCOL_SWEEP_AMPLITUDE_DEG,
            "sweep_duration_s": PROTOCOL_SWEEP_DURATION_S,
            "cadence_bpm": PROTOCOL_CADENCE_BPM,
            "reps": PROTOCOL_REPS,
            "description": PROTOCOL_REFERENCE_NOTE,
            "sources": PROTOCOL_SOURCES,
        },
        "observed": {
            "mean_sweep_amplitude_deg": amplitude,
            "mean_sweep_duration_s": duration,
            "effective_cadence_bpm": cadence_bpm,
            "sweep_duration_cv": duration_cv,
            "completed_reps": int(reps) if reps is not None else None,
            "roll_range_deg": roll,
            "pitch_range_deg": pitch,
            # True when pace came from sweeps[] rather than the aggregate field,
            # i.e. this session predates mean_sweep_duration_s.
            "pace_derived_from_sweeps": pace_derived,
        },
        "amplitude_ratio": amplitude_ratio,
        "pace_ratio": pace_ratio,
        "advisory_flags": flags,
        "comparable_to_clinical_protocol": not flags,
        "enforced_as_gates": ENFORCE_AS_GATES,
        "tolerances": {
            "amplitude_ratio_range": list(AMPLITUDE_RATIO_RANGE),
            "pace_ratio_range": list(PACE_RATIO_RANGE),
            "max_sweep_duration_cv": MAX_SWEEP_DURATION_CV,
            "max_roll_range_deg": MAX_ROLL_RANGE_DEG,
            "max_pitch_range_deg": MAX_PITCH_RANGE_DEG,
            "note": (
                "All tolerances are provisional. Amplitude and pace deviations are "
                "advisory by default because the yaw range a single webcam can "
                "track has not yet been measured."
            ),
        },
    }
