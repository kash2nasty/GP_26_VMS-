"""Composite screening severity tiers for a completed VOMS visual-motion session.

WHAT THIS IS
    A screening signal that combines the patient's self-reported symptom
    provocation with the objective gaze-instability measures from the tracker,
    and reports one of four coarse tiers. It does not identify, confirm, or rule
    out any medical condition.

WHY TIERS AND NOT A SINGLE NUMBER
    A single number implies a precision this measurement chain does not have.
    Tiers are honest about the resolution the tool can actually support and map
    cleanly onto the graded exercise suggestions in exercises.py.

THE FORMULA (see COMPOSITE_FORMULA for the machine-readable copy)

    symptom_component     = symptom_score * 10                  -> 0..100
    instability_component = 100 - fixation_stability_score       -> 0..100
    composite             = 0.60 * symptom_component
                          + 0.40 * instability_component

    tier thresholds on composite:
        composite <  20  -> minimal
        20 <= c   <  40  -> mild
        40 <= c   <  65  -> moderate
        65 <= c          -> pronounced

    Floor rule: a symptom score >= 2 can never yield "minimal". Mucha et al.
    (2014) established >= 2 on any VOMS item as a positive screening cut-off, so
    reporting "minimal" there would contradict the published anchor.

CALIBRATION STATUS -- READ THIS BEFORE TRUSTING THE NUMBERS
    The symptom side has a published anchor (the >= 2 cut-off above). The
    objective side does NOT. fixation_stability_score is bespoke to this tool and
    built on an arbitrary internal anchor (metrics.py treats 0.05 offset units of
    residual as "clearly unstable"), and residual degrees use an uncalibrated
    anatomical constant. The 0.60/0.40 weighting reflects that asymmetry in
    evidence -- the validated signal carries more weight -- but the weights
    themselves are a judgement call, not a fitted result. Every objective
    threshold below is provisional and pending local calibration against a
    reference population.

WHY SYMPTOM SCORE IS WEIGHTED HIGHER
    In the clinical VOMS protocol the patient-reported provocation IS the outcome
    measure. The objective gaze signal here is exploratory: it is the thing this
    prototype exists to evaluate, not an established index.
"""
from __future__ import annotations

from . import protocol

SCORING_SCHEMA_VERSION = "0.2.0"

# ---- tiers ---------------------------------------------------------------

TIER_MINIMAL = "minimal"
TIER_MILD = "mild"
TIER_MODERATE = "moderate"
TIER_PRONOUNCED = "pronounced"

# Ordered least -> most provoked. Used by the floor rule and by exercises.py.
TIER_ORDER = (TIER_MINIMAL, TIER_MILD, TIER_MODERATE, TIER_PRONOUNCED)

# ---- status values -------------------------------------------------------

STATUS_SCORED = "scored"                    # symptom + objective both usable
STATUS_SYMPTOM_ONLY = "symptom_only"        # objective signal not trustworthy
STATUS_OBJECTIVE_ONLY = "objective_only"    # no symptom score was provided
STATUS_INSUFFICIENT = "insufficient_data"   # neither input is usable

# ---- weights and thresholds ---------------------------------------------

SYMPTOM_WEIGHT = 0.60
INSTABILITY_WEIGHT = 0.40

# Lower bound of each tier, evaluated highest-first.
TIER_THRESHOLDS = (
    (65.0, TIER_PRONOUNCED),
    (40.0, TIER_MODERATE),
    (20.0, TIER_MILD),
    (0.0, TIER_MINIMAL),
)

# Mucha et al. 2014: >= 2 symptoms on any VOMS item is a positive screening
# cut-off. Used only as a floor, never to force a higher tier than the composite.
POSITIVE_SCREEN_SYMPTOM_SCORE = 2

# ---- data-quality gates (all provisional) --------------------------------

# Below this share of frames with a tracked face, the objective signal describes
# a recording too intermittent to characterise gaze.
MIN_FACE_DETECTION_RATE = 0.75

# compensation_r2 is how linearly the eyes counter-rotated against head yaw.
#
# CAVEAT, deliberately not hidden: a low r2 is ambiguous. It can mean the tracker
# failed, OR it can mean the patient genuinely did not fixate -- which would be
# real signal, and arguably the most interesting possible finding. Gating on it
# is the conservative choice: it discards sessions we cannot interpret rather
# than reporting a tier we cannot defend. The cost is that a genuine severe
# fixation failure may be reported as "objective signal not usable" instead of
# "pronounced". Distinguishing the two needs a second modality (e.g. per-frame
# tracking-confidence review), which this phase does not have.
MIN_COMPENSATION_R2 = 0.50

# Fewer reps than this and the protocol was not performed enough to characterise.
MIN_REPS_FOR_OBJECTIVE = 3

# Generated from the constants above rather than written out, so the formula
# reported in the output can never drift from the one actually applied. Mutation
# testing caught exactly that drift when this was a hardcoded string.
COMPOSITE_FORMULA = (
    f"composite = {SYMPTOM_WEIGHT:.2f} * (symptom_score * 10) "
    f"+ {INSTABILITY_WEIGHT:.2f} * (100 - fixation_stability_score)"
)

DISCLAIMER = (
    "This screening summary is a screening signal only. It does not identify, "
    "confirm, or rule out any medical condition, and it is not a clinical "
    "determination. Objective thresholds used here are provisional and have not "
    "been clinically validated. Results must be reviewed and interpreted by a "
    "qualified clinician in the context of a full clinical assessment."
)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _number(block, key):
    """Fetch a numeric field, treating missing AND explicit null as absent.

    Both shapes occur in real session JSON: voms_session.py emits
    {"insufficient_data": true} with every other key absent when too few frames
    were tracked, and metrics.gaze_stability() emits every key present but null
    when there were too few moving frames to fit.
    """
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _tier_for(composite: float) -> str:
    for lower_bound, tier in TIER_THRESHOLDS:
        if composite >= lower_bound:
            return tier
    return TIER_MINIMAL


def _apply_symptom_floor(tier: str, symptom_score, notes: list) -> str:
    """Never report 'minimal' for a symptom score at or above the VOMS cut-off."""
    if symptom_score is None or symptom_score < POSITIVE_SCREEN_SYMPTOM_SCORE:
        return tier
    if TIER_ORDER.index(tier) >= TIER_ORDER.index(TIER_MILD):
        return tier
    notes.append(
        f"Composite fell in the '{tier}' band, but the self-reported symptom "
        f"score of {int(symptom_score)} meets the published positive screening "
        f"cut-off (>= {POSITIVE_SCREEN_SYMPTOM_SCORE}, Mucha et al. 2014), so the "
        f"tier was raised to '{TIER_MILD}'."
    )
    return TIER_MILD


def _assess_objective(session: dict, notes: list, fidelity: dict):
    """Decide whether the objective gaze signal is usable, and why not if not.

    Returns (instability_component or None, quality_dict).
    """
    tracking = session.get("tracking_quality") or {}
    gaze = session.get("gaze_stability") or {}
    head = session.get("head_motion") or {}

    face_rate = _number(tracking, "face_detection_rate")
    r2 = _number(gaze, "compensation_r2")
    fixation = _number(gaze, "fixation_stability_score")
    reps = _number(head, "completed_reps")

    gates_failed = []

    if gaze.get("insufficient_data") is True or fixation is None:
        gates_failed.append("gaze_stability_insufficient_data")
    if face_rate is None:
        gates_failed.append("face_detection_rate_missing")
    elif face_rate < MIN_FACE_DETECTION_RATE:
        gates_failed.append("face_detection_rate_below_minimum")
    if r2 is None:
        gates_failed.append("compensation_r2_missing")
    elif r2 < MIN_COMPENSATION_R2:
        gates_failed.append("compensation_r2_below_minimum")
    if head.get("insufficient_data") is True or reps is None:
        gates_failed.append("head_motion_insufficient_data")
    elif reps < MIN_REPS_FOR_OBJECTIVE:
        gates_failed.append("too_few_completed_reps")

    # Protocol deviations are advisory by default -- see scoring/protocol.py for
    # why. Promoting them to gates is a one-constant change there.
    advisory = list(fidelity.get("advisory_flags") or [])
    if advisory and fidelity.get("enforced_as_gates"):
        gates_failed.extend(f"protocol:{flag}" for flag in advisory)

    usable = not gates_failed
    quality = {
        "face_detection_rate": face_rate,
        "compensation_r2": r2,
        "fixation_stability_score": fixation,
        "completed_reps": int(reps) if reps is not None else None,
        "frames_excluded_blink": (
            int(_number(gaze, "frames_excluded_blink") or 0)
            if _number(gaze, "frames_excluded_blink") is not None else None
        ),
        "objective_signal_usable": usable,
        "gates_failed": gates_failed,
        "protocol_advisory_flags": advisory,
        "thresholds_applied": {
            "min_face_detection_rate": MIN_FACE_DETECTION_RATE,
            "min_compensation_r2": MIN_COMPENSATION_R2,
            "min_completed_reps": MIN_REPS_FOR_OBJECTIVE,
        },
    }

    if advisory:
        notes.append(
            "This session deviated from the standardized VOMS visual-motion "
            f"protocol ({', '.join(advisory)}). The objective gaze metric is "
            "computed over whatever motion occurred, so these numbers are not "
            "comparable to published norms, and comparing them against another "
            "session is only meaningful if that session was performed at a "
            "similar amplitude and pace. See protocol_fidelity for detail."
        )

    if not usable:
        notes.append(
            "The objective gaze signal was not used because it did not pass the "
            f"data-quality gates ({', '.join(gates_failed)}). A low "
            "compensation_r2 in particular is ambiguous, because it can mean the "
            "tracker struggled or that the patient genuinely did not hold "
            "fixation, so it is reported as unusable rather than scored."
        )
        return None, quality

    return _clamp(100.0 - fixation), quality


def summarize(session: dict) -> dict:
    """Build the screening_summary block for a completed session dict.

    Never raises on malformed or partial input: an unusable session reports
    status 'insufficient_data' with severity_tier None rather than guessing.
    """
    notes: list = []

    symptoms = session.get("self_reported_symptoms") or {}
    symptom_score = _number(symptoms, "score")
    if symptom_score is not None and not 0 <= symptom_score <= 10:
        notes.append(
            f"Self-reported score {symptom_score} is outside the documented 0-10 "
            "scale and was discarded."
        )
        symptom_score = None

    fidelity = protocol.assess(session)
    instability_component, quality = _assess_objective(session, notes, fidelity)
    symptom_component = symptom_score * 10.0 if symptom_score is not None else None

    if symptom_component is not None and instability_component is not None:
        status = STATUS_SCORED
        composite = (
            SYMPTOM_WEIGHT * symptom_component
            + INSTABILITY_WEIGHT * instability_component
        )
    elif symptom_component is not None:
        status = STATUS_SYMPTOM_ONLY
        composite = symptom_component
        notes.append(
            "Tier is based on the self-reported symptom score alone; the "
            "objective gaze signal was unusable for this session."
        )
    elif instability_component is not None:
        status = STATUS_OBJECTIVE_ONLY
        composite = instability_component
        notes.append(
            "No self-reported symptom score was provided, so the tier rests "
            "entirely on the objective gaze signal, which is uncalibrated and "
            "the weaker of the two inputs. Treat this tier as provisional."
        )
    else:
        status = STATUS_INSUFFICIENT
        composite = None
        notes.append(
            "Neither a self-reported symptom score nor a usable objective gaze "
            "signal was available, so no tier was assigned. Re-run the session "
            "rather than interpreting this result."
        )

    tier = None
    if composite is not None:
        tier = _apply_symptom_floor(_tier_for(composite), symptom_score, notes)

    return {
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "status": status,
        "severity_tier": tier,
        "composite_score": round(composite, 2) if composite is not None else None,
        "components": {
            "symptom_component": (
                round(symptom_component, 2) if symptom_component is not None else None
            ),
            "instability_component": (
                round(instability_component, 2)
                if instability_component is not None else None
            ),
            "symptom_weight": SYMPTOM_WEIGHT,
            "instability_weight": INSTABILITY_WEIGHT,
        },
        "data_quality": quality,
        "protocol_fidelity": fidelity,
        "method": {
            "composite_formula": COMPOSITE_FORMULA,
            "tier_thresholds": {
                tier_name: lower for lower, tier_name in TIER_THRESHOLDS
            },
            "symptom_floor_rule": (
                f"A symptom score >= {POSITIVE_SCREEN_SYMPTOM_SCORE} is never "
                f"reported as '{TIER_MINIMAL}'."
            ),
            "calibration_status": (
                "The symptom cut-off is published (Mucha et al. 2014). All "
                "objective thresholds and the component weights are provisional "
                "and not clinically validated."
            ),
            "references": [
                "Mucha A, et al. A Brief Vestibular/Ocular Motor Screening "
                "(VOMS) Assessment to Evaluate Concussions. Am J Sports Med. "
                "2014;42(10):2479-2486.",
            ],
        },
        "notes": notes,
        "disclaimer": DISCLAIMER,
    }
