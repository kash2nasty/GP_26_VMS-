"""Tests for the screening severity tiers and exercise suggestions.

Run directly (no pytest needed):

    .venv\\Scripts\\activate
    python tests/test_scoring.py

Composite expectations below are worked out by hand from the documented formula
(composite = 0.60 * symptom*10 + 0.40 * (100 - fixation_stability_score)) and
asserted as literal numbers, so changing the weights or thresholds breaks these
tests instead of silently redefining what a tier means.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring import exercises as ex                              # noqa: E402
from scoring import protocol as prot                             # noqa: E402
from scoring import severity as sev                              # noqa: E402
from scoring.pipeline import enrich_session                      # noqa: E402

# The disclaimer already present in captured session JSON. Included in fixtures so
# the "no clinical-certainty language" test has to correctly scope itself to the
# NEW blocks rather than tripping over pre-existing passthrough text.
EXISTING_SESSION_DISCLAIMER = (
    "This output is a screening data point only and is NOT a medical diagnosis. "
    "Visual motion sensitivity cannot be diagnosed from these measurements alone."
)


def make_session(
    symptom_score=4,
    fixation=70.0,
    r2=0.95,
    face_rate=1.0,
    reps=5,
    gaze_shape="full",   # "full" | "absent_keys" | "null_values"
    head_shape="full",   # "full" | "absent_keys"
    # Head-motion defaults are deliberately protocol-faithful (160 deg sweeps at
    # 1.2 s, low off-axis motion) so the baseline fixture raises no advisory flags
    # and each deviation test has to opt in to exactly one deviation.
    amplitude=160.0,
    sweep_duration=1.2,
    sweep_cv=0.10,
    roll=15.0,
    pitch=12.0,
    blinks_excluded=0,
):
    """Build a synthetic session dict in the shape voms_session.py really emits."""
    if gaze_shape == "absent_keys":
        # What _build_result() emits when fewer than 2 frames were tracked:
        # insufficient_data alone, every other key missing entirely.
        gaze = {"insufficient_data": True}
    elif gaze_shape == "null_values":
        # What metrics.gaze_stability() emits with <10 moving frames: all keys
        # present, all values null.
        gaze = {
            "moving_frames_analyzed": 4,
            "compensation_slope": None,
            "compensation_r2": None,
            "residual_rms_offset_units": None,
            "residual_rms_deg_approx": None,
            "residual_max_offset_units": None,
            "iris_std_during_motion_offset_units": None,
            "fixation_stability_score": None,
            "insufficient_data": True,
        }
    else:
        gaze = {
            "moving_frames_analyzed": 400,
            "compensation_slope": -0.00377,
            "compensation_r2": r2,
            "residual_rms_offset_units": 0.02046,
            "residual_rms_deg_approx": 2.86,
            "residual_max_offset_units": 0.07128,
            "iris_std_during_motion_offset_units": 0.0896,
            "fixation_stability_score": fixation,
            "insufficient_data": False,
            "frames_excluded_blink": blinks_excluded,
            "min_eye_aperture_ratio": 0.15,
        }

    head = (
        {"insufficient_data": True}
        if head_shape == "absent_keys"
        else {
            "insufficient_data": False,
            "completed_reps": reps,
            "total_sweeps": reps * 2,
            "reached_target_reps": reps >= 5,
            "yaw_range_deg": amplitude / 2.0,
            "mean_sweep_amplitude_deg": amplitude,
            "mean_peak_angular_velocity_dps": 133.0,
            "mean_sweep_duration_s": sweep_duration,
            "sweep_duration_cv": sweep_cv,
            "roll_range_deg": roll,
            "pitch_range_deg": pitch,
        }
    )

    return {
        "schema_version": "0.1.0",
        "test_type": "VOMS_visual_motion_subtest",
        "disclaimer": EXISTING_SESSION_DISCLAIMER,
        "session": {"duration_s": 34.7, "target_reps": 5},
        "tracking_quality": {
            "total_frames": 611,
            "frames_with_face": 611,
            "face_detection_rate": face_rate,
            "mean_landmark_confidence": 1.0,
            "effective_fps": 17.63,
        },
        "self_reported_symptoms": {
            "scale": "0-10",
            "prompt": "Symptom provocation reported by the patient...",
            "score": symptom_score,
            "provided": symptom_score is not None,
        },
        "head_motion": head,
        "gaze_stability": gaze,
    }


def _strings(node, path="", skip_keys=()):
    """Recursively yield (path, string) pairs, skipping named subtrees."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in skip_keys:
                continue
            yield from _strings(value, f"{path}.{key}", skip_keys)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _strings(value, f"{path}[{i}]", skip_keys)
    elif isinstance(node, str):
        yield path, node


# ---- tier boundaries -----------------------------------------------------

def test_minimal_tier():
    """symptom 1 (6.0) + fixation 95 (2.0) -> composite 8.0.

    Uses symptom 1 rather than 0 deliberately: a zero symptom score multiplies the
    symptom weight away, which left an earlier version of this test unable to
    detect a change to SYMPTOM_WEIGHT at all.
    """
    out = sev.summarize(make_session(symptom_score=1, fixation=95.0))
    assert out["status"] == sev.STATUS_SCORED, out["status"]
    assert out["composite_score"] == 8.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MINIMAL, out["severity_tier"]


def test_zero_symptom_score_is_not_treated_as_missing():
    """A genuine 0 must score, not fall through to the objective-only path."""
    out = sev.summarize(make_session(symptom_score=0, fixation=95.0))
    assert out["status"] == sev.STATUS_SCORED, out["status"]
    assert out["components"]["symptom_component"] == 0.0
    assert out["composite_score"] == 2.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MINIMAL


def test_mild_tier():
    """symptom 3 (18.0) + fixation 70 (12.0) -> composite 30.0."""
    out = sev.summarize(make_session(symptom_score=3, fixation=70.0))
    assert out["composite_score"] == 30.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MILD, out["severity_tier"]


def test_moderate_tier():
    """symptom 6 (36.0) + fixation 70 (12.0) -> composite 48.0."""
    out = sev.summarize(make_session(symptom_score=6, fixation=70.0))
    assert out["composite_score"] == 48.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MODERATE, out["severity_tier"]


def test_pronounced_tier():
    """symptom 9 (54.0) + fixation 50 (20.0) -> composite 74.0."""
    out = sev.summarize(make_session(symptom_score=9, fixation=50.0))
    assert out["composite_score"] == 74.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_PRONOUNCED, out["severity_tier"]


def test_tier_boundaries_are_inclusive_lower_bounds():
    """A composite landing exactly on a threshold takes the higher tier."""
    # symptom 0, fixation 50 -> 0.4 * 50 = 20.0, exactly the mild lower bound.
    out = sev.summarize(make_session(symptom_score=0, fixation=50.0))
    assert out["composite_score"] == 20.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MILD, out["severity_tier"]


# ---- the published symptom floor -----------------------------------------

def test_symptom_floor_prevents_minimal():
    """symptom 2 with perfect fixation -> composite 12.0, but must not be minimal.

    Mucha et al. 2014 established >= 2 as a positive screening cut-off, so
    reporting 'minimal' there would contradict the published anchor.
    """
    out = sev.summarize(make_session(symptom_score=2, fixation=100.0))
    assert out["composite_score"] == 12.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MILD, out["severity_tier"]
    assert any("cut-off" in n for n in out["notes"]), out["notes"]


def test_symptom_floor_does_not_lower_a_higher_tier():
    """The floor only raises; it must never pull a worse tier down to mild."""
    out = sev.summarize(make_session(symptom_score=9, fixation=50.0))
    assert out["severity_tier"] == sev.TIER_PRONOUNCED, out["severity_tier"]


def test_symptom_one_stays_minimal():
    """Just below the cut-off, the floor must not fire."""
    out = sev.summarize(make_session(symptom_score=1, fixation=100.0))
    assert out["composite_score"] == 6.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MINIMAL, out["severity_tier"]


# ---- data-quality gates --------------------------------------------------

def test_low_face_detection_rate_gates_objective_signal():
    out = sev.summarize(make_session(symptom_score=6, face_rate=0.40))
    assert out["status"] == sev.STATUS_SYMPTOM_ONLY, out["status"]
    assert "face_detection_rate_below_minimum" in out["data_quality"]["gates_failed"]
    assert out["data_quality"]["objective_signal_usable"] is False
    assert out["components"]["instability_component"] is None
    # Tier now rests on the symptom score alone: 6 * 10 = 60.0 -> moderate.
    assert out["composite_score"] == 60.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MODERATE, out["severity_tier"]


def test_low_compensation_r2_gates_objective_signal():
    """This is the pre-sign-fix failure mode: r2 collapsed near zero."""
    out = sev.summarize(make_session(symptom_score=4, r2=0.0166))
    assert out["status"] == sev.STATUS_SYMPTOM_ONLY, out["status"]
    assert "compensation_r2_below_minimum" in out["data_quality"]["gates_failed"]
    assert out["composite_score"] == 40.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_MODERATE, out["severity_tier"]


def test_good_r2_passes_the_gate():
    """Guards the gate against being trivially always-on."""
    out = sev.summarize(make_session(symptom_score=4, r2=0.9479))
    assert out["status"] == sev.STATUS_SCORED, out["status"]
    assert out["data_quality"]["gates_failed"] == []
    assert out["data_quality"]["objective_signal_usable"] is True


def test_too_few_reps_gates_objective_signal():
    out = sev.summarize(make_session(symptom_score=5, reps=1))
    assert out["status"] == sev.STATUS_SYMPTOM_ONLY, out["status"]
    assert "too_few_completed_reps" in out["data_quality"]["gates_failed"]


def test_gate_failures_are_reported_not_silent():
    """An unusable objective signal must be visible in the output, not dropped."""
    out = sev.summarize(make_session(symptom_score=5, face_rate=0.2, r2=0.01))
    gates = out["data_quality"]["gates_failed"]
    assert len(gates) >= 2, gates
    assert any("objective gaze signal was not used" in n for n in out["notes"])


# ---- insufficient data ---------------------------------------------------

def test_insufficient_when_gaze_keys_absent_and_no_symptom_score():
    """The shape voms_session.py emits when fewer than 2 frames tracked."""
    out = sev.summarize(make_session(
        symptom_score=None, gaze_shape="absent_keys", head_shape="absent_keys",
    ))
    assert out["status"] == sev.STATUS_INSUFFICIENT, out["status"]
    assert out["severity_tier"] is None
    assert out["composite_score"] is None
    assert any("Re-run the session" in n for n in out["notes"]), out["notes"]


def test_insufficient_when_gaze_values_null_and_no_symptom_score():
    """The other real shape: keys present, values null, <10 moving frames."""
    out = sev.summarize(make_session(symptom_score=None, gaze_shape="null_values"))
    assert out["status"] == sev.STATUS_INSUFFICIENT, out["status"]
    assert out["severity_tier"] is None


def test_symptom_score_survives_unusable_objective_data():
    """A patient-reported score is still worth reporting on its own."""
    out = sev.summarize(make_session(symptom_score=8, gaze_shape="absent_keys"))
    assert out["status"] == sev.STATUS_SYMPTOM_ONLY, out["status"]
    assert out["composite_score"] == 80.0, out["composite_score"]
    assert out["severity_tier"] == sev.TIER_PRONOUNCED, out["severity_tier"]


def test_objective_only_is_flagged_as_provisional():
    out = sev.summarize(make_session(symptom_score=None, fixation=30.0))
    assert out["status"] == sev.STATUS_OBJECTIVE_ONLY, out["status"]
    assert out["composite_score"] == 70.0, out["composite_score"]
    assert any("provisional" in n for n in out["notes"]), out["notes"]


def test_out_of_range_symptom_score_is_discarded():
    out = sev.summarize(make_session(symptom_score=15))
    assert out["status"] == sev.STATUS_OBJECTIVE_ONLY, out["status"]
    assert out["components"]["symptom_component"] is None
    assert any("outside the documented 0-10" in n for n in out["notes"])


def test_summarize_never_raises_on_garbage():
    for bad in ({}, {"gaze_stability": None}, {"self_reported_symptoms": {}},
                {"tracking_quality": "nonsense", "head_motion": []}):
        out = sev.summarize(bad)
        assert out["status"] == sev.STATUS_INSUFFICIENT, (bad, out["status"])
        assert out["severity_tier"] is None


# ---- exercise mapping ----------------------------------------------------

def test_every_tier_has_exercises():
    for tier in sev.TIER_ORDER:
        rec = ex.recommend(tier)
        assert rec["exercises"], tier
        assert rec["severity_tier"] == tier


def test_exercise_entries_are_complete():
    """Each recommendation carries name, description, frequency and rationale."""
    for tier in sev.TIER_ORDER:
        for item in ex.recommend(tier)["exercises"]:
            for field in ("name", "description", "suggested_frequency",
                          "rationale", "protocol_stage"):
                assert item.get(field), f"{tier}/{item.get('id')} missing {field}"


def test_all_referenced_exercises_exist_in_catalogue():
    """Guards against a typo'd key in TIER_PLANS reaching output."""
    for tier, plan in ex.TIER_PLANS.items():
        for key, _rationale in plan["exercises"]:
            assert key in ex.EXERCISE_CATALOGUE, f"{tier} references unknown {key}"


def test_pronounced_tier_withholds_head_rotation():
    """The safety inversion: the provoking movement is not in the starting set.

    Sustained head rotation is what the subtest uses to provoke symptoms. At the
    most-provoked tier it is deliberately withheld pending clinician review, so a
    naive tier -> difficulty mapping cannot hand the most symptomatic person the
    most aggressive protocol.
    """
    ids = [e["id"] for e in ex.recommend(sev.TIER_PRONOUNCED)["exercises"]]
    assert "head_turn_side_to_side" not in ids, ids
    assert "walk_with_head_turns" not in ids, ids


def test_severity_inverts_exercise_load():
    """More provoked -> fewer, gentler exercises; less provoked -> more."""
    counts = {t: len(ex.recommend(t)["exercises"]) for t in sev.TIER_ORDER}
    assert counts[sev.TIER_PRONOUNCED] < counts[sev.TIER_MODERATE], counts
    assert counts[sev.TIER_MODERATE] < counts[sev.TIER_MILD], counts


def test_pronounced_tier_is_seated_only():
    """No standing or walking work in the most conservative starting set."""
    stages = {
        e["protocol_stage"] for e in ex.recommend(sev.TIER_PRONOUNCED)["exercises"]
    }
    assert not any("Standing" in s or "Moving" in s for s in stages), stages


def test_no_tier_yields_no_exercises():
    """Never suggest physical exercises off data we could not interpret."""
    rec = ex.recommend(None, sev.STATUS_INSUFFICIENT)
    assert rec["exercises"] == []
    assert "insufficient" in rec["summary"].lower()


def test_unknown_tier_yields_no_exercises():
    rec = ex.recommend("catastrophic")
    assert rec["exercises"] == []
    assert "Unrecognised" in rec["summary"]


# ---- framing and disclaimers --------------------------------------------

def test_all_new_blocks_carry_a_disclaimer():
    enriched = enrich_session(make_session(symptom_score=6))
    assert enriched["screening_summary"]["disclaimer"]
    assert enriched["recommended_exercises"]["disclaimer"]
    assert enriched["recommended_exercises"]["safety_note"]


def test_no_tier_output_still_carries_disclaimers():
    """The insufficient-data path must not skip the safety text."""
    enriched = enrich_session(make_session(
        symptom_score=None, gaze_shape="absent_keys", head_shape="absent_keys",
    ))
    assert enriched["screening_summary"]["disclaimer"]
    assert enriched["recommended_exercises"]["disclaimer"]
    assert enriched["recommended_exercises"]["safety_note"]


def test_new_blocks_avoid_clinical_certainty_language():
    """No diagnostic framing anywhere in the blocks this phase produces.

    Scoped to screening_summary and recommended_exercises only: the top-level
    session `disclaimer` is pre-existing passthrough text that uses the word in a
    negation ("is NOT a medical diagnosis"), and this phase does not rewrite it.

    URLs are stripped before matching. A third-party citation URL can contain a
    banned substring in its path (balanceanddizziness.org has
    /diagnosis-and-treatment/) without that being clinical framing in our output,
    and dropping the citation to satisfy a substring check would cost real
    auditability for no safety gain.
    """
    banned = ("diagnos", "confirms that", "proves", "definitely", "certainly")
    url_pattern = re.compile(r"https?://\S+")
    for block_name in ("screening_summary", "recommended_exercises"):
        for tier_case in (6, None):
            enriched = enrich_session(make_session(symptom_score=tier_case))
            for path, text in _strings(enriched[block_name], block_name):
                prose = url_pattern.sub("", text).lower()
                for word in banned:
                    assert word not in prose, f"{path}: {word!r} in {text!r}"


# Written as code points rather than as the characters themselves, so this file can
# enforce the convention without containing what it bans. That is not fussiness: a
# pass over the repository that replaced literal dashes with ASCII rewrote these
# needles too, which silently turned the em-dash check into a check for a plain
# hyphen and made it fail on the page range in a citation. chr() cannot be caught by
# that class of edit.
BANNED_DASHES = {
    "em dash": chr(0x2014),
    "en dash": chr(0x2013),
    "double hyphen": "--",
}

# Every block of the enriched output that a reader ever sees.
USER_FACING_BLOCKS = (
    "screening_summary",
    "screening_indications",
    "recommended_exercises",
)


def test_no_em_dashes_in_user_facing_text():
    """House style: no em dashes, en dashes, or ASCII double hyphens in copy.

    These strings are authored in Python and rendered verbatim by the web UI, so
    this is the only place the convention can actually be enforced. Comments and
    docstrings are exempt by construction, since this walks the built output rather
    than the source.
    """
    for tier_case in (6, None, 0):
        enriched = enrich_session(make_session(symptom_score=tier_case))
        for block_name in USER_FACING_BLOCKS:
            for path, text in _strings(enriched[block_name], block_name):
                for label, needle in BANNED_DASHES.items():
                    assert needle not in text, f"{label} in {path}: {text!r}"


def test_no_em_dashes_in_insufficient_data_text():
    """The insufficient-data path has its own copy, so it needs its own check."""
    enriched = enrich_session(make_session(
        symptom_score=None, gaze_shape="absent_keys", head_shape="absent_keys",
    ))
    for block_name in USER_FACING_BLOCKS:
        for path, text in _strings(enriched[block_name], block_name):
            for label, needle in BANNED_DASHES.items():
                assert needle not in text, f"{label} in {path}: {text!r}"


def test_exercise_blocks_cite_the_protocol():
    rec = ex.recommend(sev.TIER_MODERATE)
    assert rec["protocol"] == ex.PROTOCOL_NAME
    assert rec["protocol_references"]
    assert any("Cooksey" in r for r in rec["protocol_references"])


# ---- pipeline ------------------------------------------------------------

def test_enrich_preserves_original_session_data():
    session = make_session(symptom_score=6)
    enriched = enrich_session(session)
    for key, value in session.items():
        assert enriched[key] == value, key
    assert "screening_summary" not in session, "input dict was mutated"
    assert "recommended_exercises" not in session, "input dict was mutated"


def test_enrich_ties_exercises_to_the_scored_tier():
    enriched = enrich_session(make_session(symptom_score=9, fixation=50.0))
    tier = enriched["screening_summary"]["severity_tier"]
    assert tier == sev.TIER_PRONOUNCED
    assert enriched["recommended_exercises"]["severity_tier"] == tier


def test_method_block_documents_the_formula():
    """The logic must be auditable from the output, not just the source."""
    method = sev.summarize(make_session())["method"]
    assert set(method["tier_thresholds"]) == set(sev.TIER_ORDER)
    assert method["tier_thresholds"][sev.TIER_PRONOUNCED] == 65.0
    assert "not clinically validated" in method["calibration_status"]
    assert any("Mucha" in r for r in method["references"])
    assert str(sev.POSITIVE_SCREEN_SYMPTOM_SCORE) in method["symptom_floor_rule"]


def test_reported_weights_reproduce_the_reported_composite():
    """The weights shown in the output must be the ones actually applied.

    Catches the class of bug where the composite is computed with one weight but
    the output documents another -- which is what made the formula unauditable
    when COMPOSITE_FORMULA was a hardcoded string.
    """
    out = sev.summarize(make_session(symptom_score=6, fixation=70.0))
    parts = out["components"]
    recomputed = (
        parts["symptom_weight"] * parts["symptom_component"]
        + parts["instability_weight"] * parts["instability_component"]
    )
    assert round(recomputed, 2) == out["composite_score"], (
        f"reported weights give {recomputed}, output says {out['composite_score']}"
    )
    formula = out["method"]["composite_formula"]
    assert f"{parts['symptom_weight']:.2f}" in formula, formula
    assert f"{parts['instability_weight']:.2f}" in formula, formula


# ---- protocol fidelity ---------------------------------------------------

def test_protocol_faithful_session_raises_no_flags():
    """Guards the deviation tests against a fixture that always deviates."""
    fid = prot.assess(make_session())
    assert fid["advisory_flags"] == [], fid["advisory_flags"]
    assert fid["comparable_to_clinical_protocol"] is True
    assert fid["amplitude_ratio"] == 1.0, fid["amplitude_ratio"]
    assert fid["pace_ratio"] == 1.0, fid["pace_ratio"]


def test_reference_matches_published_protocol():
    """80 deg each side => 160 deg per sweep; 50 bpm => 1.2 s per sweep."""
    ref = prot.assess(make_session())["reference"]
    assert ref["sweep_amplitude_deg"] == 160.0
    assert ref["cadence_bpm"] == 50.0
    assert round(ref["sweep_duration_s"], 3) == 1.2
    assert ref["reps"] == 5


def test_low_amplitude_is_flagged():
    fid = prot.assess(make_session(amplitude=76.0))
    assert "amplitude_below_protocol" in fid["advisory_flags"], fid["advisory_flags"]
    assert fid["comparable_to_clinical_protocol"] is False


def test_high_amplitude_is_flagged():
    fid = prot.assess(make_session(amplitude=220.0))
    assert "amplitude_above_protocol" in fid["advisory_flags"]


def test_slow_pace_is_flagged():
    """A longer sweep duration is a slower pace."""
    fid = prot.assess(make_session(sweep_duration=2.94))
    assert "pace_slower_than_protocol" in fid["advisory_flags"], fid["advisory_flags"]
    assert fid["pace_ratio"] < 1.0, fid["pace_ratio"]
    assert fid["observed"]["effective_cadence_bpm"] < 50.0


def test_fast_pace_is_flagged():
    fid = prot.assess(make_session(sweep_duration=0.5))
    assert "pace_faster_than_protocol" in fid["advisory_flags"]
    assert fid["pace_ratio"] > 1.0


def test_inconsistent_pace_is_flagged():
    fid = prot.assess(make_session(sweep_cv=0.60))
    assert "pace_inconsistent_within_session" in fid["advisory_flags"]


def test_excessive_off_axis_motion_is_flagged():
    assert "excessive_roll" in prot.assess(make_session(roll=58.6))["advisory_flags"]
    assert "excessive_pitch" in prot.assess(make_session(pitch=30.1))["advisory_flags"]


def test_clean_off_axis_motion_is_not_flagged():
    flags = prot.assess(make_session(roll=20.0, pitch=15.0))["advisory_flags"]
    assert "excessive_roll" not in flags
    assert "excessive_pitch" not in flags


def test_fewer_reps_than_protocol_is_flagged():
    assert "fewer_reps_than_protocol" in prot.assess(
        make_session(reps=3)
    )["advisory_flags"]


def test_missing_head_motion_reports_unknown_not_compliant():
    """Absent data must never read as protocol-faithful."""
    fid = prot.assess(make_session(head_shape="absent_keys"))
    assert "amplitude_unknown" in fid["advisory_flags"]
    assert "pace_unknown" in fid["advisory_flags"]
    assert fid["comparable_to_clinical_protocol"] is False


def test_real_measured_session_deviates_from_protocol():
    """Pinned to the actual capture: ~76 deg sweeps at ~1.65 s, roll ~58.6 deg.

    The tool previously reported a tier off this motion with no indication it was
    at roughly half protocol amplitude.
    """
    fid = prot.assess(make_session(
        amplitude=75.83, sweep_duration=1.6527, sweep_cv=0.163,
        roll=58.62, pitch=30.14,
    ))
    assert "amplitude_below_protocol" in fid["advisory_flags"]
    assert "excessive_roll" in fid["advisory_flags"]
    assert "excessive_pitch" in fid["advisory_flags"]
    # Pace was within tolerance and intra-session CV was steady.
    assert "pace_slower_than_protocol" not in fid["advisory_flags"]
    assert "pace_inconsistent_within_session" not in fid["advisory_flags"]
    assert fid["comparable_to_clinical_protocol"] is False


def test_pace_is_recovered_from_sweeps_for_older_sessions():
    """A pre-upgrade capture has sweeps[] but no aggregate pace fields."""
    session = make_session(amplitude=75.83)
    head = session["head_motion"]
    del head["mean_sweep_duration_s"]
    del head["sweep_duration_cv"]
    head["sweeps"] = [
        {"duration_s": d} for d in
        (1.855, 2.097, 1.855, 1.713, 1.648, 1.648, 1.552, 1.712, 1.391, 1.056)
    ]

    fid = prot.assess(session)
    assert fid["observed"]["pace_derived_from_sweeps"] is True
    assert fid["observed"]["mean_sweep_duration_s"] == 1.653, (
        fid["observed"]["mean_sweep_duration_s"]
    )
    assert fid["observed"]["sweep_duration_cv"] == 0.1625, (
        fid["observed"]["sweep_duration_cv"]
    )
    assert "pace_unknown" not in fid["advisory_flags"], fid["advisory_flags"]


def test_pace_unknown_when_no_sweeps_either():
    session = make_session()
    del session["head_motion"]["mean_sweep_duration_s"]
    fid = prot.assess(session)
    assert "pace_unknown" in fid["advisory_flags"]
    assert fid["observed"]["pace_derived_from_sweeps"] is False


def test_aggregate_pace_field_wins_over_sweeps():
    """When both exist, the aggregate is authoritative and nothing is 'derived'."""
    session = make_session()
    session["head_motion"]["sweeps"] = [{"duration_s": 9.9} for _ in range(10)]
    fid = prot.assess(session)
    assert fid["observed"]["pace_derived_from_sweeps"] is False
    assert fid["observed"]["mean_sweep_duration_s"] == 1.2


def test_fidelity_block_is_attached_to_the_summary():
    out = sev.summarize(make_session(amplitude=76.0))
    assert "protocol_fidelity" in out
    assert out["protocol_fidelity"]["comparable_to_clinical_protocol"] is False
    assert out["data_quality"]["protocol_advisory_flags"]


def test_protocol_deviation_is_surfaced_in_notes():
    out = sev.summarize(make_session(amplitude=76.0))
    assert any("deviated from the standardized" in n for n in out["notes"]), out["notes"]
    assert any("not comparable to published norms" in n for n in out["notes"])


def test_protocol_deviation_does_not_block_scoring_by_default():
    """Advisory by default: the objective signal still contributes."""
    out = sev.summarize(make_session(symptom_score=8, fixation=31.6, amplitude=76.0))
    assert out["status"] == sev.STATUS_SCORED, out["status"]
    assert out["data_quality"]["objective_signal_usable"] is True
    assert out["data_quality"]["gates_failed"] == []
    assert out["composite_score"] == 75.36, out["composite_score"]


def test_protocol_deviation_blocks_scoring_when_enforced():
    """Flipping ENFORCE_AS_GATES promotes advisories to blocking gates."""
    original = prot.ENFORCE_AS_GATES
    prot.ENFORCE_AS_GATES = True
    try:
        out = sev.summarize(make_session(symptom_score=8, amplitude=76.0))
        assert out["status"] == sev.STATUS_SYMPTOM_ONLY, out["status"]
        assert out["data_quality"]["objective_signal_usable"] is False
        assert any(g.startswith("protocol:") for g in out["data_quality"]["gates_failed"])
    finally:
        prot.ENFORCE_AS_GATES = original


def test_blink_exclusion_count_reaches_the_summary():
    out = sev.summarize(make_session(blinks_excluded=7))
    assert out["data_quality"]["frames_excluded_blink"] == 7


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures.append((fn.__name__, exc))
            print(f"  FAIL  {fn.__name__}")
        else:
            print(f"  PASS  {fn.__name__}")

    if failures:
        for name, exc in failures:
            print(f"\n--- {name} ---\n{exc}")
        print(f"\n{len(failures)} of {len(tests)} failed")
        return 1

    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
