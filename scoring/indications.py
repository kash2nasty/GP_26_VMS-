"""Multi-signal screening indications from one capture.

WHAT CHANGED AND WHY
    This project began as a digitizer for a single test: the visual-motion subtest
    of VOMS, which asks one question about one thing. But the capture it takes to
    answer that question contains the raw material for several other well-described
    clinical signs, and session/signals.py now measures them. This module turns
    those measurements into a panel of screening indications.

    The value is not that any single indication is strong. It is that a person who
    sat down for a 30 second head-rotation test gets checked for a one-sided
    vestibular pattern, involuntary eye oscillation, ocular misalignment, an
    eyelid that droops under fatigue, an abnormal blink rate, resting facial
    asymmetry, restricted neck rotation and head tremor at the same time, for free,
    from frames that were already on disk.

WHAT AN "INDICATION" IS AND IS NOT
    An indication is: a named measurement crossed a stated threshold, here is the
    number, here is the threshold, here is what that pattern is associated with,
    and here is what a clinician might do about it.

    An indication is NOT a diagnosis, a probability, or a finding. This tool has a
    webcam, no calibration, one axis of head movement and about thirty seconds. It
    cannot diagnose anything, and several of the conditions named below are
    diagnosed by tests that look nothing like this one. Every indication therefore
    reports `finding` as one of indicated / not_indicated / not_assessable, and
    "not_indicated" means only that this particular measurement did not cross this
    particular threshold in this particular session. It is never a clearance.

THE THREE RULES THAT KEEP THIS HONEST
    1. NO SILENT NULLS. If a signal could not be measured, the indication says
       not_assessable and says why. Reporting "not indicated" off missing data
       would turn an absence of measurement into a reassurance, which is the single
       most harmful thing a screening tool can do.
    2. EVERY THRESHOLD IS REPORTED. The number that was measured and the number it
       was compared against both travel in the output, so a reader can disagree
       with the threshold without having to read this file.
    3. EVIDENCE BASIS IS LABELLED. `evidence_basis` distinguishes an indication
       built on a published sign with a provisional threshold from one built on a
       metric invented in this repository. Two of these are the former; most are
       the latter, and the reader is told which is which.

URGENCY, AND WHY IT IS NOT A TRIAGE SYSTEM
    Two of the signs here (vertical ocular misalignment and resting facial
    asymmetry) overlap with presentations that are emergencies when they are NEW.
    This tool cannot tell new from long-standing, and it cannot triage a stroke.
    So those indications carry urgency "emergency_if_new" with wording that puts
    the judgement where it belongs: with a person who can ask when it started.
    Nothing here should ever be the reason someone does not call for help, and
    nothing here is sufficient reason to say someone is fine.
"""
from __future__ import annotations

INDICATIONS_SCHEMA_VERSION = "0.1.0"

# ---- vocabulary -----------------------------------------------------------

FINDING_INDICATED = "indicated"
FINDING_NOT_INDICATED = "not_indicated"
FINDING_NOT_ASSESSABLE = "not_assessable"

STRENGTH_BORDERLINE = "borderline"
STRENGTH_PRESENT = "present"
STRENGTH_MARKED = "marked"

URGENCY_ROUTINE = "routine"
URGENCY_PROMPT = "prompt"
URGENCY_EMERGENCY_IF_NEW = "emergency_if_new"

URGENCY_ORDER = (URGENCY_ROUTINE, URGENCY_PROMPT, URGENCY_EMERGENCY_IF_NEW)

BASIS_PUBLISHED_SIGN = "published_sign_provisional_threshold"
BASIS_BESPOKE_METRIC = "bespoke_metric_arbitrary_threshold"

# The check that restates the test the capture was actually run for, as opposed to
# the ones this module added on top of it.
#
# It is marked because it is already reported everywhere else: it IS the severity
# tier. A list view that counted it alongside the rest showed "1 flagged" against
# every session that was not 'minimal' and printed "motion sensitivity" in a column
# immediately beside the tier badge saying the same thing. Callers that want "what
# did we find BEYOND the subtest" read `secondary_indicated`.
PRIMARY_CHECK_IDS = ("visual_motion_sensitivity",)

# ---- shared gates ---------------------------------------------------------

# Below this share of frames with a tracked face, nothing derived from the
# landmarks describes the person rather than the tracker.
MIN_FACE_DETECTION_RATE = 0.75

# Anything rhythmic needs several samples per cycle. A capture slower than this
# cannot support the frequency work at all, and saying so is more useful than
# reporting a number computed at the Nyquist edge.
#
# This is checked against the sample rate the signal blocks derive from frame
# TIMESTAMPS, not against tracking_quality.effective_fps. The latter is frames over
# wall-clock session duration, which is the right number for "did the capture keep
# up" and the wrong one for Nyquist: it counts undetected frames and is skewed by
# any pause. Only the timestamp spacing says how densely the movement was actually
# sampled.
MIN_FPS_FOR_FREQUENCY = 20.0

# ---- per-indication thresholds, all provisional ---------------------------

# Directional asymmetry of gaze stabilisation, as (difference / sum) of the
# residual RMS in each direction. 0 is symmetric, 1 is entirely one-sided.
ASYMMETRY_BORDERLINE = 0.20
ASYMMETRY_PRESENT = 0.30
ASYMMETRY_MARKED = 0.50
MIN_SWEEPS_PER_DIRECTION = 2

# Rhythmic eye oscillation. Rhythmicity is the share of in-band spectral power in
# the peak, so it rises with periodicity rather than with size.
OSCILLATION_RHYTHMICITY = 0.30
OSCILLATION_AMPLITUDE_OFFSET_UNITS = 0.008

# Fixation breaks per second of session. A normally performed subtest produces
# very few: the eyes either track smoothly or they do not.
FIXATION_BREAK_RATE_BORDERLINE = 0.8
FIXATION_BREAK_RATE_PRESENT = 1.5

# Interocular disparity in socket-normalised units. Deliberately loose, because an
# uncalibrated constant bias from the landmark model sits inside the mean.
HORIZONTAL_DISPARITY = 0.045
VERTICAL_DISPARITY = 0.030

# Eyelid opening difference between the two eyes, over their mean.
APERTURE_ASYMMETRY_BORDERLINE = 0.15
APERTURE_ASYMMETRY_PRESENT = 0.25

# Relative fall in eyelid opening from the first third of the session to the last.
APERTURE_DECLINE = 0.15

# Blinks per minute. Resting norms cluster near 8 to 21 per minute, but this is a
# demanding visual task, during which blink rate is known to fall, so the low
# bound is set well under the resting range on purpose.
BLINK_RATE_LOW = 5.0
BLINK_RATE_HIGH = 32.0

# Resting facial asymmetry in face-width units. A symmetric face measures near 0;
# nobody measures exactly 0.
FACIAL_ASYMMETRY_BORDERLINE = 0.020
FACIAL_ASYMMETRY_PRESENT = 0.035
MIN_FRONTAL_FRAMES = 30

# Cervical rotation. The protocol asks for 80 degrees each side, so 160 total.
#
# TWO THRESHOLDS, AND WHY THE GAP BETWEEN THEM IS UNASSESSABLE
#     A single front-facing webcam loses the face somewhere before profile, and
#     this project has not yet measured where (check_yaw_ceiling.py exists to find
#     out). So a session that stopped at 100 degrees might be a neck that would not
#     turn further or a tracker that stopped following, and there is no way to tell
#     from the recording. Reporting restriction anywhere under the protocol
#     amplitude made this indication fire on essentially every capture, which is
#     worse than useless: an indication that is always on carries no information and
#     trains the reader to ignore the panel.
#
#     Below SEVERE the ambiguity goes away. At 30 degrees to each side the face is
#     still close to frontal and well inside anything a webcam can track, so a
#     range that small is about the person. Between the two bounds the honest answer
#     is that this capture cannot say, and that is what gets reported.
YAW_RANGE_RESTRICTED_DEG = 90.0
YAW_RANGE_SEVERE_DEG = 60.0
OFF_AXIS_COUPLING_HIGH = 0.60

# Head tremor. The band searched is 2.5 to 6 Hz (see session/signals.py), bounded
# by frame rate rather than by physiology.
TREMOR_RHYTHMICITY = 0.35
TREMOR_AMPLITUDE_DEG = 0.8

DISCLAIMER = (
    "These indications are screening observations from a single webcam capture. "
    "They do not identify, confirm, or rule out any medical condition, they are "
    "not a clinical determination, and a result of 'not indicated' is not a "
    "clearance: it means only that one measurement did not cross one provisional "
    "threshold in one session. Every threshold here is uncalibrated and none has "
    "been clinically validated. All of it must be reviewed by a qualified "
    "clinician alongside a full assessment."
)

EMERGENCY_NOTE = (
    "Some of the signs on this panel overlap with presentations that are medical "
    "emergencies when they appear suddenly, including stroke. This tool cannot "
    "tell a new sign from a long-standing one and cannot triage anybody. If facial "
    "weakness, double vision, new severe dizziness, slurred speech or limb weakness "
    "came on suddenly, seek emergency care now and do not wait for a screening "
    "result. Equally, nothing on this panel is a reason to believe someone is fine."
)


# ---- helpers --------------------------------------------------------------

def _block(session, name):
    value = session.get(name) if isinstance(session, dict) else None
    return value if isinstance(value, dict) else {}


def _num(block, key):
    """Numeric field, treating missing, null and bool alike as absent."""
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _indication(
    id,
    label,
    screens_for,
    finding,
    *,
    strength=None,
    measured=None,
    thresholds=None,
    interpretation="",
    reason=None,
    urgency=URGENCY_ROUTINE,
    evidence_basis=BASIS_BESPOKE_METRIC,
    caveat=None,
    next_step=None,
    references=(),
):
    return {
        "id": id,
        "label": label,
        # The condition families this pattern is associated with. Named so a
        # reader knows what is being screened for, never asserted as present.
        "screens_for": list(screens_for),
        # True for the check that restates the subtest itself. See PRIMARY_CHECK_IDS.
        "is_primary": id in PRIMARY_CHECK_IDS,
        "finding": finding,
        "strength": strength,
        "measured": dict(measured or {}),
        "thresholds": dict(thresholds or {}),
        "interpretation": interpretation,
        # Why the signal could not be assessed. Only set for not_assessable.
        "reason": reason,
        "urgency": urgency if finding == FINDING_INDICATED else URGENCY_ROUTINE,
        "evidence_basis": evidence_basis,
        "caveat": caveat,
        "next_step": next_step,
        "references": list(references),
    }


def _sample_rate(block, tracking):
    """Sampling rate to judge a frequency result against.

    Prefers the rate the signal block derived from frame timestamps, and falls back
    to the wall-clock effective_fps only when a session predates that field.
    """
    rate = _num(block, "sample_rate_hz")
    return rate if rate is not None else _num(tracking, "effective_fps")


def _graded(value, borderline, present, marked=None):
    """Strength band for a value compared against ascending thresholds."""
    if marked is not None and value >= marked:
        return STRENGTH_MARKED
    if value >= present:
        return STRENGTH_PRESENT
    if value >= borderline:
        return STRENGTH_BORDERLINE
    return None


# ---- the panel ------------------------------------------------------------

def _visual_motion_sensitivity(session, summary):
    """The original subtest, restated as one entry on the panel."""
    tier = summary.get("severity_tier") if isinstance(summary, dict) else None
    status = summary.get("status") if isinstance(summary, dict) else None
    composite = _num(summary if isinstance(summary, dict) else {}, "composite_score")

    common = dict(
        id="visual_motion_sensitivity",
        label="Visual motion sensitivity",
        screens_for=[
            "visual motion sensitivity as defined by the VOMS protocol",
            "vestibular contribution to persistent post-concussion symptoms",
            "vestibular migraine",
        ],
        evidence_basis=BASIS_PUBLISHED_SIGN,
        references=[
            "Mucha A, et al. A Brief Vestibular/Ocular Motor Screening (VOMS) "
            "Assessment to Evaluate Concussions. Am J Sports Med. "
            "2014;42(10):2479-2486.",
        ],
    )

    if tier is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            reason=(
                "No screening tier was assigned for this session "
                f"(status: {status}), so the subtest itself did not produce a "
                "result to report."
            ),
            **common,
        )

    indicated = tier != "minimal"
    return _indication(
        finding=FINDING_INDICATED if indicated else FINDING_NOT_INDICATED,
        strength={
            "mild": STRENGTH_BORDERLINE,
            "moderate": STRENGTH_PRESENT,
            "pronounced": STRENGTH_MARKED,
        }.get(tier) if indicated else None,
        measured={"severity_tier": tier, "composite_score": composite},
        thresholds={"tier_above": "minimal"},
        interpretation=(
            f"The composite screening tier for this session was '{tier}'. "
            "This is the result the capture was designed to produce and the only "
            "entry on this panel with a published symptom anchor behind it."
        ),
        caveat=(
            "The objective half of the composite is uncalibrated. See "
            "screening_summary.method for the formula and its calibration status."
        ),
        next_step=(
            "Review alongside the rest of the VOMS battery, which this tool does "
            "not administer: smooth pursuit, saccades, convergence and the "
            "vestibulo-ocular reflex subtests."
        ),
        **common,
    )


def _vestibular_asymmetry(session, summary):
    head = _block(session, "head_control")
    quality = _block(summary, "data_quality") if isinstance(summary, dict) else {}

    common = dict(
        id="vestibular_asymmetry",
        label="Direction-dependent gaze instability",
        screens_for=[
            "unilateral peripheral vestibular hypofunction",
            "recovering vestibular neuritis or labyrinthitis",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Halmagyi GM, Curthoys IS. A clinical sign of canal paresis. Arch "
            "Neurol. 1988;45(7):737-739.",
        ],
    )
    thresholds = {
        "asymmetry_index_borderline": ASYMMETRY_BORDERLINE,
        "asymmetry_index_present": ASYMMETRY_PRESENT,
        "asymmetry_index_marked": ASYMMETRY_MARKED,
        "min_sweeps_per_direction": MIN_SWEEPS_PER_DIRECTION,
    }

    index = _num(head, "direction_asymmetry_index")
    leftward = _num(head, "leftward_sweeps") or 0
    rightward = _num(head, "rightward_sweeps") or 0

    if index is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Gaze residual could not be split by direction. This session "
                "either predates the wider signal set or did not contain usable "
                "sweeps in both directions."
            ),
            **common,
        )
    if min(leftward, rightward) < MIN_SWEEPS_PER_DIRECTION:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            measured={"leftward_sweeps": leftward, "rightward_sweeps": rightward},
            reason=(
                f"Only {int(leftward)} leftward and {int(rightward)} rightward "
                "sweeps were recorded. Comparing directions needs at least "
                f"{MIN_SWEEPS_PER_DIRECTION} of each."
            ),
            **common,
        )
    if quality.get("objective_signal_usable") is False:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            measured={"direction_asymmetry_index": index},
            reason=(
                "The objective gaze signal failed the data-quality gates for this "
                "session, so a difference between directions cannot be separated "
                "from tracking noise."
            ),
            **common,
        )

    strength = _graded(index, ASYMMETRY_BORDERLINE, ASYMMETRY_PRESENT, ASYMMETRY_MARKED)
    measured = {
        "direction_asymmetry_index": index,
        "leftward_residual_rms_offset_units": _num(
            head, "leftward_residual_rms_offset_units"
        ),
        "rightward_residual_rms_offset_units": _num(
            head, "rightward_residual_rms_offset_units"
        ),
        "velocity_asymmetry_index": _num(head, "velocity_asymmetry_index"),
    }

    if strength is None:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "Gaze stabilisation behaved similarly turning each way "
                f"(asymmetry index {index:.2f}), which is what a symmetric "
                "vestibular response looks like on this measure."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=strength,
        measured=measured,
        thresholds=thresholds,
        urgency=URGENCY_ROUTINE,
        interpretation=(
            f"Gaze was markedly less stable turning one way than the other "
            f"(asymmetry index {index:.2f}). A one-sided difference is the pattern "
            "a one-sided vestibular loss produces, and it is invisible to the "
            "whole-session average the subtest normally reports: a session that is "
            "fine one way and poor the other averages out to look merely mediocre."
        ),
        caveat=(
            "A one-sided difference in head movement effort, uneven lighting across "
            "the face, or the subject turning further one way than the other "
            "produces the same reading. Check velocity_asymmetry_index: if the two "
            "directions were also performed at different speeds, the gaze difference "
            "may be a consequence of that rather than of vestibular function."
        ),
        next_step=(
            "This pattern is what the head impulse test and caloric or video head "
            "impulse testing are designed to resolve. Neither is performed here."
        ),
        **common,
    )


def _rhythmic_eye_oscillation(session, summary):
    ocular = _block(session, "oculomotor_signals")
    head = _block(session, "head_control")
    tracking = _block(session, "tracking_quality")

    common = dict(
        id="rhythmic_eye_oscillation",
        label="Rhythmic eye oscillation",
        screens_for=[
            "nystagmus of vestibular origin",
            "central oculomotor disorder",
            "oscillopsia",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Strupp M, et al. Central ocular motor disorders. J Neurol. "
            "2014;261(Suppl 2):S542-S558.",
        ],
    )
    thresholds = {
        "rhythmicity": OSCILLATION_RHYTHMICITY,
        "amplitude_offset_units": OSCILLATION_AMPLITUDE_OFFSET_UNITS,
        "band_hz": ocular.get("oscillation_band_hz"),
        "min_fps": MIN_FPS_FOR_FREQUENCY,
    }

    fps = _sample_rate(ocular, tracking)
    rhythmicity = _num(ocular, "oscillation_rhythmicity")
    frequency = _num(ocular, "oscillation_frequency_hz")
    amplitude = _num(ocular, "oscillation_amplitude_offset_units")

    if rhythmicity is None or frequency is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "No frequency estimate was produced. The session was either too "
                "short for the band searched, sampled too slowly, or predates the "
                "wider signal set."
            ),
            **common,
        )
    if fps is not None and fps < MIN_FPS_FOR_FREQUENCY:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            measured={"sample_rate_hz": fps},
            reason=(
                f"Frames arrived at {fps:.1f} per second. Nystagmus "
                "frequencies sit at or above half that rate, so this session "
                "cannot exclude it and cannot measure it. Recapture at "
                f"{MIN_FPS_FOR_FREQUENCY:.0f} fps or more to assess this."
            ),
            **common,
        )

    measured = {
        "oscillation_frequency_hz": frequency,
        "oscillation_rhythmicity": rhythmicity,
        "oscillation_amplitude_offset_units": amplitude,
        "sample_rate_hz": fps,
    }

    indicated = (
        rhythmicity >= OSCILLATION_RHYTHMICITY
        and amplitude is not None
        and amplitude >= OSCILLATION_AMPLITUDE_OFFSET_UNITS
    )
    if not indicated:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "Eye movement not explained by smooth compensation had no strong "
                f"periodic component in the band searched (rhythmicity "
                f"{rhythmicity:.2f}). Faster oscillation than this capture can "
                "sample would not appear here at all."
            ),
            **common,
        )

    # A head tremor drives a compensating eye movement at its own frequency, so an
    # oscillation matching one already measured in the head is very likely to be
    # that rather than an independent eye finding.
    tremor_hz = _num(head, "tremor_frequency_hz")
    tremor_rhythmicity = _num(head, "tremor_rhythmicity")
    head_driven = (
        tremor_hz is not None
        and tremor_rhythmicity is not None
        and tremor_rhythmicity >= TREMOR_RHYTHMICITY
        and abs(tremor_hz - frequency) < 0.6
    )
    if head_driven:
        measured["matching_head_tremor_hz"] = tremor_hz
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                f"A periodic eye component was found at {frequency:.1f} Hz, but the "
                f"head was itself oscillating at {tremor_hz:.1f} Hz. The eyes moving "
                "at the frequency the head is moving at is compensation working, not "
                "an independent eye finding, so this is reported under head tremor "
                "instead of here."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT if rhythmicity < 0.6 else STRENGTH_MARKED,
        measured=measured,
        thresholds=thresholds,
        urgency=URGENCY_PROMPT,
        interpretation=(
            f"Eye movement contained a strong periodic component at "
            f"{frequency:.1f} Hz that smooth compensation for head rotation does "
            f"not explain (rhythmicity {rhythmicity:.2f}). Rhythmic involuntary eye "
            "movement is what the word nystagmus describes."
        ),
        caveat=(
            "A webcam sampling a few times faster than the oscillation itself is "
            "close to the limit of what can be measured, and periodic tracker error "
            "at the sweep rate can imitate this. Direction, waveform and the effect "
            "of gaze position, which is how nystagmus is actually characterised, "
            "are all invisible here."
        ),
        next_step=(
            "Direct observation of the eyes, ideally with fixation removed, is what "
            "distinguishes this from a tracking artifact."
        ),
        **common,
    )


def _fixation_breakdown(session, summary):
    ocular = _block(session, "oculomotor_signals")
    quality = _block(summary, "data_quality") if isinstance(summary, dict) else {}

    common = dict(
        id="fixation_breakdown",
        label="Frequent fixation breaks",
        screens_for=[
            "saccadic intrusion into smooth pursuit",
            "oculomotor sequelae of concussion",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Mucha A, et al. A Brief Vestibular/Ocular Motor Screening (VOMS) "
            "Assessment to Evaluate Concussions. Am J Sports Med. "
            "2014;42(10):2479-2486.",
        ],
    )
    thresholds = {
        "rate_per_s_borderline": FIXATION_BREAK_RATE_BORDERLINE,
        "rate_per_s_present": FIXATION_BREAK_RATE_PRESENT,
    }

    rate = _num(ocular, "fixation_break_rate_per_s")
    if rate is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Fixation breaks were not counted for this session, which predates "
                "the wider signal set or produced no usable gaze fit."
            ),
            **common,
        )
    if quality.get("objective_signal_usable") is False:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            measured={"fixation_break_rate_per_s": rate},
            reason=(
                "The gaze signal failed its data-quality gates, so breaks away from "
                "the fitted line cannot be told apart from tracking failure."
            ),
            **common,
        )

    measured = {
        "fixation_break_rate_per_s": rate,
        "fixation_break_count": _num(ocular, "fixation_break_count"),
        "largest_fixation_break_offset_units": _num(
            ocular, "largest_fixation_break_offset_units"
        ),
    }
    strength = _graded(rate, FIXATION_BREAK_RATE_BORDERLINE, FIXATION_BREAK_RATE_PRESENT)
    if strength is None:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                f"Gaze left the smoothly compensating path {rate:.2f} times per "
                "second, which is in the range a normally performed subtest "
                "produces."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=strength,
        measured=measured,
        thresholds=thresholds,
        interpretation=(
            f"Gaze broke away from smooth compensation {rate:.2f} times per second. "
            "Repeated small jumps back onto the target, rather than continuous "
            "tracking, is the pattern described as saccadic intrusion."
        ),
        caveat=(
            "The subject looking at the screen instead of their thumb produces "
            "exactly this, and so does a head rotating faster than the eyes can "
            "smoothly follow. Both are performance issues rather than findings."
        ),
        next_step=(
            "The smooth pursuit and saccade subtests of VOMS test this directly. "
            "This tool administers neither."
        ),
        **common,
    )


def _horizontal_misalignment(session, summary):
    alignment = _block(session, "ocular_alignment")

    common = dict(
        id="horizontal_ocular_misalignment",
        label="Horizontal eye alignment difference",
        screens_for=[
            "horizontal strabismus (esotropia or exotropia)",
            "convergence insufficiency",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Wright KW, Strube YNJ. Pediatric Ophthalmology and Strabismus. "
            "3rd ed. Oxford University Press; 2012.",
        ],
    )
    thresholds = {"mean_disparity_offset_units": HORIZONTAL_DISPARITY}

    disparity = _num(alignment, "horizontal_disparity_mean_offset_units")
    if disparity is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Both irises were not located in enough frames to compare where the "
                "two eyes were pointing."
            ),
            **common,
        )

    measured = {
        "horizontal_disparity_mean_offset_units": disparity,
        "horizontal_disparity_std_offset_units": _num(
            alignment, "horizontal_disparity_std_offset_units"
        ),
        "frames_analyzed": _num(alignment, "frames_analyzed"),
    }
    if abs(disparity) < HORIZONTAL_DISPARITY:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "The two eyes pointed within the measurable tolerance of each other "
                "horizontally. That tolerance is wide, because an uncalibrated "
                "landmark bias sits inside this number, so a small deviation would "
                "not show up here."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT if abs(disparity) < 2 * HORIZONTAL_DISPARITY else STRENGTH_MARKED,
        measured=measured,
        thresholds=thresholds,
        interpretation=(
            f"The two eyes differed by {disparity:+.3f} socket-normalised units "
            "horizontally, sustained across the session. A consistent difference in "
            "where the two eyes point is what a horizontal deviation looks like."
        ),
        caveat=(
            "The landmark model does not locate both sockets with identical "
            "accuracy, and that constant error is inside this figure. A cover test "
            "takes seconds and settles the question properly."
        ),
        next_step="Cover test and orthoptic assessment.",
        **common,
    )


def _vertical_misalignment(session, summary):
    alignment = _block(session, "ocular_alignment")

    common = dict(
        id="vertical_ocular_misalignment",
        label="Vertical eye alignment difference",
        screens_for=[
            "skew deviation and ocular tilt reaction",
            "fourth cranial nerve palsy",
            "brainstem or cerebellar involvement",
        ],
        evidence_basis=BASIS_PUBLISHED_SIGN,
        references=[
            "Kattah JC, et al. HINTS to diagnose stroke in the acute vestibular "
            "syndrome. Stroke. 2009;40(11):3504-3510.",
        ],
    )
    thresholds = {"mean_disparity_offset_units": VERTICAL_DISPARITY}

    disparity = _num(alignment, "vertical_disparity_mean_offset_units")
    if disparity is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Vertical iris positions were not available for both eyes in enough "
                "frames. Sessions captured before the wider signal set existed never "
                "recorded this."
            ),
            **common,
        )

    measured = {
        "vertical_disparity_mean_offset_units": disparity,
        "vertical_disparity_std_offset_units": _num(
            alignment, "vertical_disparity_std_offset_units"
        ),
        "vertical_disparity_max_offset_units": _num(
            alignment, "vertical_disparity_max_offset_units"
        ),
        "frames_analyzed": _num(alignment, "frames_analyzed"),
    }
    if abs(disparity) < VERTICAL_DISPARITY:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "No sustained vertical difference between the eyes was measured. "
                "This is the more clinically interesting of the two alignment "
                "checks, because vertical misalignment is a central sign rather "
                "than a refractive one."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT if abs(disparity) < 2 * VERTICAL_DISPARITY else STRENGTH_MARKED,
        measured=measured,
        thresholds=thresholds,
        urgency=URGENCY_EMERGENCY_IF_NEW,
        interpretation=(
            f"The two eyes sat {disparity:+.3f} socket-normalised units apart "
            "vertically across the session. Vertical misalignment, unlike "
            "horizontal, is associated with central rather than refractive causes, "
            "and it is one component of the HINTS examination used to separate a "
            "peripheral vestibular problem from a stroke."
        ),
        caveat=(
            "This is a webcam measurement with an uncalibrated landmark bias in it, "
            "not the test-of-skew part of a HINTS examination, which requires "
            "alternate cover by an examiner. A false positive here is entirely "
            "possible and this measurement alone means very little."
        ),
        next_step=(
            "Alternate cover test. If this is new and came with sudden severe "
            "dizziness, treat it as the emergency presentation it can be."
        ),
        **common,
    )


def _eyelid_asymmetry(session, summary):
    eyelid = _block(session, "eyelid_signals")

    common = dict(
        id="eyelid_asymmetry",
        label="Eyelid opening asymmetry",
        screens_for=[
            "ptosis",
            "third cranial nerve palsy",
            "Horner syndrome",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Finsterer J. Ptosis: causes, presentation, and management. Aesthetic "
            "Plast Surg. 2003;27(3):193-204.",
        ],
    )
    thresholds = {
        "asymmetry_ratio_borderline": APERTURE_ASYMMETRY_BORDERLINE,
        "asymmetry_ratio_present": APERTURE_ASYMMETRY_PRESENT,
    }

    ratio = _num(eyelid, "aperture_asymmetry_ratio")
    if ratio is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Eyelid opening was not measured for both eyes in enough open-eye "
                "frames."
            ),
            **common,
        )

    measured = {
        "aperture_asymmetry_ratio": ratio,
        "left_aperture_median": _num(eyelid, "left_aperture_median"),
        "right_aperture_median": _num(eyelid, "right_aperture_median"),
    }
    strength = _graded(ratio, APERTURE_ASYMMETRY_BORDERLINE, APERTURE_ASYMMETRY_PRESENT)
    if strength is None:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                f"The two eyelids opened to within {ratio * 100:.0f}% of each other, "
                "which is inside normal variation."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=strength,
        measured=measured,
        thresholds=thresholds,
        urgency=URGENCY_ROUTINE if strength == STRENGTH_BORDERLINE else URGENCY_PROMPT,
        interpretation=(
            f"One eyelid opened {ratio * 100:.0f}% less than the other throughout "
            "the session. A persistent difference in lid opening is what ptosis "
            "describes."
        ),
        caveat=(
            "Camera angle, a head held slightly turned, and asymmetric lighting all "
            "produce this. Side labels here have not been verified against the "
            "subject's anatomical left and right, so read the magnitude and confirm "
            "the side by looking at the person."
        ),
        next_step=(
            "Direct measurement of the palpebral fissure and margin reflex "
            "distance, and history for when it started."
        ),
        **common,
    )


def _fatigable_eyelid_droop(session, summary):
    eyelid = _block(session, "eyelid_signals")

    common = dict(
        id="fatigable_eyelid_droop",
        label="Eyelid droop increasing through the session",
        screens_for=[
            "fatigable ptosis as seen in myasthenia gravis",
            "ocular myopathy",
        ],
        evidence_basis=BASIS_PUBLISHED_SIGN,
        references=[
            "Kubis KC, et al. The ice test versus the rest test in myasthenia "
            "gravis. Ophthalmology. 2000;107(11):1995-1998.",
        ],
    )
    thresholds = {
        "relative_decline": APERTURE_DECLINE,
        "min_session_s": 20.0,
    }

    decline = _num(eyelid, "aperture_relative_decline")
    if decline is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "The session was too short, or had too few open-eye frames, to "
                "compare eyelid opening at the start against the end. Sustained "
                "effort is the whole point of this check, so a brief capture cannot "
                "provide it."
            ),
            **common,
        )

    measured = {
        "aperture_relative_decline": decline,
        "aperture_trend_per_min": _num(eyelid, "aperture_trend_per_min"),
        "fatigue_window_s": _num(eyelid, "fatigue_window_s"),
    }
    if decline < APERTURE_DECLINE:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "Eyelid opening held up across the session "
                f"(change of {decline * 100:+.0f}% from start to end), so no "
                "fatigable droop was measured over this duration."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT if decline < 2 * APERTURE_DECLINE else STRENGTH_MARKED,
        measured=measured,
        thresholds=thresholds,
        urgency=URGENCY_PROMPT,
        interpretation=(
            f"Eyelid opening fell {decline * 100:.0f}% from the start of the session "
            "to the end. A droop that appears with sustained effort and was not "
            "there at the beginning is specifically described as fatigable, which is "
            "a different observation from a droop that is simply present."
        ),
        caveat=(
            "Sitting more comfortably, drifting closer to or further from the "
            "camera, or simply relaxing the face as a demanding task ends will all "
            "reduce measured lid opening. Thirty seconds is also a very short "
            "fatigue challenge compared with the sustained upgaze normally used."
        ),
        next_step=(
            "Sustained upgaze for one to two minutes with the lid watched directly, "
            "and history for daily variation, is the standard bedside version of "
            "this observation."
        ),
        **common,
    )


def _blink_rate(session, summary):
    ocular = _block(session, "oculomotor_signals")

    common = dict(
        id="blink_rate_abnormality",
        label="Blink rate outside the expected range",
        screens_for=[
            "reduced blink rate as seen in hypokinetic movement disorders",
            "ocular surface irritation or dry eye",
            "blepharospasm",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Bentivoglio AR, et al. Analysis of blink rate patterns in normal "
            "subjects. Mov Disord. 1997;12(6):1028-1034.",
        ],
    )
    thresholds = {"low_per_min": BLINK_RATE_LOW, "high_per_min": BLINK_RATE_HIGH}

    rate = _num(ocular, "blink_rate_per_min")
    if rate is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Blinks were not counted for this session. Captures made before "
                "eyelid aperture was recorded cannot support this."
            ),
            **common,
        )

    measured = {
        "blink_rate_per_min": rate,
        "blink_count": _num(ocular, "blink_count"),
        "mean_blink_duration_s": _num(ocular, "mean_blink_duration_s"),
    }
    low = rate < BLINK_RATE_LOW
    high = rate > BLINK_RATE_HIGH
    if not (low or high):
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                f"Blink rate was {rate:.0f} per minute during the task, inside the "
                "range this tool treats as unremarkable."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT,
        measured=measured,
        thresholds=thresholds,
        interpretation=(
            f"Blink rate was {rate:.0f} per minute, "
            + (
                "below the range expected even for a demanding visual task. A "
                "persistently reduced blink rate is one of the recognised signs of "
                "hypokinetic movement disorders."
                if low else
                "above the expected range. An elevated rate is more often about the "
                "surface of the eye than about the brain, and screen glare or a dry "
                "room will do it."
            )
        ),
        caveat=(
            "Blink rate falls during any demanding visual task, and this test is "
            "one, so a single short capture is weak evidence in either direction. "
            "Rate also varies with humidity, contact lenses, and how hard someone "
            "is concentrating."
        ),
        next_step=(
            "Observation at rest over a longer period, which is how blink rate "
            "norms were established in the first place."
        ),
        **common,
    )


def _facial_asymmetry(session, summary):
    facial = _block(session, "facial_symmetry")

    common = dict(
        id="facial_asymmetry",
        label="Resting facial asymmetry",
        screens_for=[
            "facial nerve palsy, including Bell palsy",
            "facial weakness as a stroke sign",
        ],
        evidence_basis=BASIS_PUBLISHED_SIGN,
        references=[
            "Nor NM, et al. The FAST test for stroke recognition. Stroke. "
            "1998;29(9):1885-1889.",
            "House JW, Brackmann DE. Facial nerve grading system. Otolaryngol Head "
            "Neck Surg. 1985;93(2):146-147.",
        ],
    )
    thresholds = {
        "asymmetry_borderline": FACIAL_ASYMMETRY_BORDERLINE,
        "asymmetry_present": FACIAL_ASYMMETRY_PRESENT,
        "min_frontal_frames": MIN_FRONTAL_FRAMES,
    }

    mouth = _num(facial, "mouth_corner_asymmetry")
    frames = _num(facial, "frames_analyzed") or 0
    if mouth is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "Facial symmetry was not measured. It is only computed on frames "
                "where the head was near frontal, and a test built entirely out of "
                "turning the head can contain very few of those."
            ),
            **common,
        )
    if frames < MIN_FRONTAL_FRAMES:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            measured={"frames_analyzed": frames, "mouth_corner_asymmetry": mouth},
            reason=(
                f"Only {int(frames)} near-frontal frames were available, under the "
                f"{MIN_FRONTAL_FRAMES} needed for a stable measurement. Ask the "
                "subject to face the camera squarely for a few seconds before the "
                "sweeps begin."
            ),
            **common,
        )

    measured = {
        "mouth_corner_asymmetry": mouth,
        "brow_height_asymmetry": _num(facial, "brow_height_asymmetry"),
        "mouth_corner_asymmetry_spread": _num(
            facial, "mouth_corner_asymmetry_spread"
        ),
        "frames_analyzed": frames,
    }
    strength = _graded(
        abs(mouth), FACIAL_ASYMMETRY_BORDERLINE, FACIAL_ASYMMETRY_PRESENT
    )
    if strength is None:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "The two sides of the mouth sat at comparable heights across the "
                "near-frontal frames. This measures the face at rest only, and says "
                "nothing about weakness that appears on movement, which is how "
                "facial nerve function is normally graded."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=strength,
        measured=measured,
        thresholds=thresholds,
        urgency=URGENCY_EMERGENCY_IF_NEW,
        interpretation=(
            f"One side of the mouth sat {abs(mouth):.3f} face-widths lower than the "
            "other at rest. Asymmetry of the lower face is the sign the F in FAST "
            "stands for, and it is also the presenting sign of facial nerve palsy."
        ),
        caveat=(
            "Almost nobody is perfectly symmetric, and a long-standing difference "
            "measures identically to a new one. Camera angle and expression both "
            "shift this reading. Side labels have not been verified against the "
            "subject's anatomical sides."
        ),
        next_step=(
            "Look at the person and ask them to smile, raise their eyebrows and "
            "close their eyes tightly. If this is NEW, it is an emergency "
            "presentation, and a screening tool is not the right instrument: seek "
            "emergency care."
        ),
        **common,
    )


def _cervical_restriction(session, summary):
    head_motion = _block(session, "head_motion")
    head_control = _block(session, "head_control")
    fidelity = _block(summary, "protocol_fidelity") if isinstance(summary, dict) else {}

    common = dict(
        id="cervical_rotation_restriction",
        label="Restricted neck rotation",
        screens_for=[
            "cervical spine rotation restriction",
            "cervicogenic dizziness",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Reiley AS, et al. How to diagnose cervicogenic dizziness. Arch "
            "Physiother. 2017;7:12.",
        ],
    )
    thresholds = {
        "yaw_range_unremarkable_above_deg": YAW_RANGE_RESTRICTED_DEG,
        "yaw_range_restricted_below_deg": YAW_RANGE_SEVERE_DEG,
        "off_axis_coupling_high": OFF_AXIS_COUPLING_HIGH,
    }

    yaw_range = _num(head_motion, "yaw_range_deg")
    coupling = _num(head_control, "off_axis_coupling_ratio")
    if yaw_range is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason="No head rotation range was recorded for this session.",
            **common,
        )

    measured = {
        "yaw_range_deg": yaw_range,
        "off_axis_coupling_ratio": coupling,
        "mean_sweep_amplitude_deg": _num(head_motion, "mean_sweep_amplitude_deg"),
        "amplitude_ratio": _num(fidelity, "amplitude_ratio"),
    }
    coupled = coupling is not None and coupling > OFF_AXIS_COUPLING_HIGH

    if yaw_range >= YAW_RANGE_RESTRICTED_DEG:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                f"Total rotation reached {yaw_range:.0f} degrees, which does not "
                "suggest a mechanical limit on turning the head."
            ),
            **common,
        )

    if yaw_range >= YAW_RANGE_SEVERE_DEG:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            measured=measured,
            thresholds=thresholds,
            reason=(
                f"Total rotation reached {yaw_range:.0f} degrees, short of the 160 "
                "the protocol asks for but inside the range where a webcam may "
                "simply have stopped following the face. The yaw a single "
                "front-facing camera can track has not been measured in this "
                "project, so a limit in this range cannot be attributed to the neck "
                "rather than to the tracker."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT if coupled else STRENGTH_BORDERLINE,
        measured=measured,
        thresholds=thresholds,
        interpretation=(
            f"Total rotation reached only {yaw_range:.0f} degrees against the "
            "160 the protocol asks for. At this amplitude the face stays near "
            "frontal throughout, so the tracker was not the limit"
            + (
                f", and off-axis movement was high (coupling {coupling:.2f}), "
                "meaning the head tilted and nodded rather than turning. "
                "Substituting tilt for rotation is what people do when rotation "
                "itself is limited or uncomfortable."
                if coupled else
                ". Off-axis movement was not raised, so this may still be how far "
                "the subject chose to turn rather than how far they could."
            )
        ),
        caveat=(
            "A subject who did not understand the instruction, was being cautious, "
            "or was avoiding provoking symptoms produces exactly this reading. "
            "Restricted rotation measured here is not evidence of a neck problem on "
            "its own, only evidence that the head did not turn far."
        ),
        next_step=(
            "Goniometric cervical range of motion, and the cervical torsion test if "
            "dizziness is the complaint."
        ),
        **common,
    )


def _head_tremor(session, summary):
    head = _block(session, "head_control")
    tracking = _block(session, "tracking_quality")

    common = dict(
        id="head_tremor",
        label="Rhythmic head oscillation",
        screens_for=[
            "essential head tremor",
            "cerebellar titubation",
            "cervical dystonia with tremor",
        ],
        evidence_basis=BASIS_BESPOKE_METRIC,
        references=[
            "Bhatia KP, et al. Consensus Statement on the classification of "
            "tremors. Mov Disord. 2018;33(1):75-87.",
        ],
    )
    thresholds = {
        "rhythmicity": TREMOR_RHYTHMICITY,
        "amplitude_deg": TREMOR_AMPLITUDE_DEG,
        "band_hz": head.get("tremor_band_hz"),
        "min_fps": MIN_FPS_FOR_FREQUENCY,
    }

    frequency = _num(head, "tremor_frequency_hz")
    rhythmicity = _num(head, "tremor_rhythmicity")
    amplitude = _num(head, "tremor_amplitude_deg")
    fps = _sample_rate(head, tracking)

    if frequency is None or rhythmicity is None:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            reason=(
                "No head oscillation estimate was produced, because the session was "
                "too short or too slowly sampled for the band searched."
            ),
            **common,
        )
    if fps is not None and fps < MIN_FPS_FOR_FREQUENCY:
        return _indication(
            finding=FINDING_NOT_ASSESSABLE,
            thresholds=thresholds,
            measured={"sample_rate_hz": fps},
            reason=(
                f"Frames arrived at {fps:.1f} per second, too slow to measure "
                "oscillation in the tremor band."
            ),
            **common,
        )

    measured = {
        "tremor_frequency_hz": frequency,
        "tremor_rhythmicity": rhythmicity,
        "tremor_amplitude_deg": amplitude,
        "sample_rate_hz": fps,
    }
    indicated = (
        rhythmicity >= TREMOR_RHYTHMICITY
        and amplitude is not None
        and amplitude >= TREMOR_AMPLITUDE_DEG
    )
    if not indicated:
        return _indication(
            finding=FINDING_NOT_INDICATED,
            measured=measured,
            thresholds=thresholds,
            interpretation=(
                "Head movement contained no strong rhythmic component riding on the "
                f"sweeps (rhythmicity {rhythmicity:.2f}, amplitude "
                f"{amplitude if amplitude is not None else 0:.2f} degrees)."
            ),
            **common,
        )

    return _indication(
        finding=FINDING_INDICATED,
        strength=STRENGTH_PRESENT if amplitude < 2 * TREMOR_AMPLITUDE_DEG else STRENGTH_MARKED,
        measured=measured,
        thresholds=thresholds,
        interpretation=(
            f"A rhythmic oscillation of about {amplitude:.1f} degrees at "
            f"{frequency:.1f} Hz rode on top of the intended head sweeps. Rhythmic "
            "involuntary head movement is what head tremor describes."
        ),
        caveat=(
            "Rotating the head deliberately at close to a metronome beat can put "
            "energy in this band, and so can a hand-held or vibrating camera. The "
            "band searched stops at 6 Hz because of the frame rate, not because "
            "tremor does."
        ),
        next_step=(
            "Observation of the head at rest and with the arms outstretched, which "
            "is how tremor is classified."
        ),
        **common,
    )


CHECKS = (
    _visual_motion_sensitivity,
    _vestibular_asymmetry,
    _rhythmic_eye_oscillation,
    _fixation_breakdown,
    _horizontal_misalignment,
    _vertical_misalignment,
    _eyelid_asymmetry,
    _fatigable_eyelid_droop,
    _blink_rate,
    _facial_asymmetry,
    _cervical_restriction,
    _head_tremor,
)


# ---- entry point ----------------------------------------------------------

def assess(session: dict, summary: dict | None = None) -> dict:
    """Run every check against one session and return the whole panel.

    Never raises. A check that cannot run reports not_assessable, and a check that
    throws is reported as not_assessable with the error text rather than taking the
    session down: a broken new indication must not be able to hide the VOMS result
    the capture was actually run for.
    """
    session = session if isinstance(session, dict) else {}
    summary = summary if isinstance(summary, dict) else {}

    tracking = _block(session, "tracking_quality")
    face_rate = _num(tracking, "face_detection_rate")
    tracking_ok = face_rate is None or face_rate >= MIN_FACE_DETECTION_RATE

    panel = []
    for check in CHECKS:
        try:
            entry = check(session, summary)
        except Exception as exc:  # noqa: BLE001 - a broken check must not break the page
            entry = _indication(
                id=getattr(check, "__name__", "unknown").strip("_"),
                label="Check failed",
                screens_for=[],
                finding=FINDING_NOT_ASSESSABLE,
                reason=f"This check raised an error and was skipped: {exc}",
            )
        # A recording too intermittent to characterise anything downgrades every
        # measured finding at once, rather than each check re-deriving that.
        if not tracking_ok and entry["finding"] == FINDING_INDICATED:
            entry = dict(entry)
            entry["finding"] = FINDING_NOT_ASSESSABLE
            entry["strength"] = None
            entry["urgency"] = URGENCY_ROUTINE
            entry["reason"] = (
                f"A face was tracked in only {face_rate * 100:.0f}% of frames, below "
                f"the {MIN_FACE_DETECTION_RATE * 100:.0f}% needed for any landmark "
                "measurement to describe the person rather than the tracker. The "
                "underlying numbers are still reported under 'measured'."
            )
        panel.append(entry)

    indicated = [e["id"] for e in panel if e["finding"] == FINDING_INDICATED]
    not_assessable = [e["id"] for e in panel if e["finding"] == FINDING_NOT_ASSESSABLE]
    secondary = [i for i in indicated if i not in PRIMARY_CHECK_IDS]
    urgencies = [
        e["urgency"] for e in panel if e["finding"] == FINDING_INDICATED
    ]
    highest = None
    for level in reversed(URGENCY_ORDER):
        if level in urgencies:
            highest = level
            break

    return {
        "schema_version": INDICATIONS_SCHEMA_VERSION,
        "panel": panel,
        "checks_run": len(panel),
        "indicated": indicated,
        # Flagged checks other than the subtest itself, which the severity tier
        # already reports. See PRIMARY_CHECK_IDS.
        "secondary_indicated": secondary,
        "secondary_checks_run": len(panel) - len(PRIMARY_CHECK_IDS),
        "not_assessable": not_assessable,
        "highest_urgency": highest,
        "summary": _summary_line(len(panel), secondary, not_assessable),
        "tracking_sufficient": tracking_ok,
        "disclaimer": DISCLAIMER,
        "emergency_note": EMERGENCY_NOTE,
        "method": {
            "what_an_indication_means": (
                "A named measurement crossed a stated threshold. Both numbers are "
                "reported so the threshold can be disagreed with. This is not a "
                "diagnosis, a probability, or a finding."
            ),
            "what_not_indicated_means": (
                "One measurement did not cross one provisional threshold in one "
                "session. It is not a clearance and not evidence of absence."
            ),
            "evidence_basis_values": {
                BASIS_PUBLISHED_SIGN: (
                    "The sign is described in the literature; the threshold applied "
                    "to it here is provisional and set by this project."
                ),
                BASIS_BESPOKE_METRIC: (
                    "Both the metric and the threshold originate in this project "
                    "and neither has been validated against anything."
                ),
            },
            "shared_gates": {
                "min_face_detection_rate": MIN_FACE_DETECTION_RATE,
                "min_fps_for_frequency": MIN_FPS_FOR_FREQUENCY,
            },
        },
    }


def _summary_line(total, secondary_indicated, not_assessable):
    """One sentence describing what the panel found beyond the subtest itself.

    Counted over the secondary checks, not all of them, for the same reason
    PRIMARY_CHECK_IDS exists: the primary check restates the severity tier, so
    including it here reported "1 of 12 flagged" for every session that was not
    'minimal' and said nothing the tier had not already said.
    """
    scope = total - len(PRIMARY_CHECK_IDS)
    parts = []
    if secondary_indicated:
        parts.append(
            f"{len(secondary_indicated)} of {scope} checks beyond the subtest "
            "flagged a signal worth a look"
        )
    else:
        parts.append(
            f"No signal crossed a threshold on the {scope} checks beyond the "
            "subtest, which is not a clearance"
        )
    if not_assessable:
        parts.append(
            f"{len(not_assessable)} could not be assessed from this capture"
        )
    return ". ".join(parts) + "."
