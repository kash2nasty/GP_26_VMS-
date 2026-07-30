"""Tests for the wider signal set and the screening indications panel.

Run directly (no pytest needed):

    .venv\\Scripts\\activate
    python tests/test_indications.py

WHAT THESE TESTS ARE FOR
    session/signals.py measures several things that were not previously measured,
    and scoring/indications.py decides what to say about them. The risk in both is
    not that a number comes out slightly wrong: it is that a signal is reported as
    absent when it is present, or present when the capture could not have seen it.
    So each check gets three tests where possible: a clean session must NOT trigger
    it, a session with the thing injected MUST trigger it, and a session missing the
    input data must come back not_assessable rather than not_indicated.

    That third case is the one worth the most. "not_indicated" off missing data is a
    false reassurance, which is the worst failure mode a screening tool has.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring import indications                                   # noqa: E402
from scoring.pipeline import enrich_session                        # noqa: E402
from session import metrics, signals                               # noqa: E402
from session.voms_session import SessionConfig, VOMSSession        # noqa: E402
from tracking.face_tracker import FrameRecord, facial_symmetry     # noqa: E402
from tracking import landmarks as LM                               # noqa: E402

OPEN_APERTURE = 0.30
CLOSED_APERTURE = 0.04


# ---- fixtures -------------------------------------------------------------

def build_session(
    *,
    fps=30.0,
    duration_s=26.0,
    sweep_amplitude_deg=60.0,
    sweep_period_s=3.0,
    vor_gain=-0.004,
    blink_every_s=5.0,
    blink_frames=4,
    nystagmus_amplitude=0.0,
    nystagmus_hz=3.0,
    tremor_deg=0.0,
    tremor_hz=4.0,
    horizontal_disparity=0.0,
    vertical_disparity=0.0,
    lid_ratio=1.0,
    lid_decline=0.0,
    face_asymmetry=0.0,
    direction_penalty=0.0,
    symptom_score=1,
    roll_deg=0.0,
    with_apertures=True,
    with_symmetry=True,
):
    """One synthetic session with any subset of signals injected.

    Defaults describe a well-performed capture with nothing wrong: a smooth sinusoid
    of head yaw, eyes counter-rotating in exact proportion, a normal blink every few
    seconds, and a symmetric face. Every keyword adds exactly one abnormality, so a
    test that injects one thing and sees two indications has found a cross-talk bug.
    """
    session = VOMSSession(config=SessionConfig(target_reps=99, max_duration_s=1e6))
    session.start_session()

    blink_period = max(1, int(fps * blink_every_s))
    total = int(fps * duration_s)

    for index in range(total):
        t = index / fps
        progress = t / duration_s
        yaw = sweep_amplitude_deg * math.sin(2 * math.pi * t / sweep_period_s)
        if tremor_deg:
            yaw += tremor_deg * math.sin(2 * math.pi * tremor_hz * t)

        offset = vor_gain * yaw
        if nystagmus_amplitude:
            offset += nystagmus_amplitude * math.sin(2 * math.pi * nystagmus_hz * t)
        # A one-sided vestibular pattern: extra unexplained eye motion only while
        # the head travels one way.
        if direction_penalty and math.cos(2 * math.pi * t / sweep_period_s) > 0:
            offset += direction_penalty * math.sin(2 * math.pi * 7.0 * t)

        blinking = (index % blink_period) < blink_frames
        aperture = CLOSED_APERTURE if blinking else OPEN_APERTURE
        # lid_decline drops BOTH lids, so it injects fatigue without also injecting
        # asymmetry. lid_ratio injects asymmetry without also injecting fatigue.
        # One knob, one abnormality: a test that turns one on and sees two
        # indications has found cross-talk rather than a finding.
        fatigue = 1.0 - lid_decline * progress
        left_aperture = aperture * fatigue
        right_aperture = aperture * fatigue * lid_ratio

        near_frontal = abs(yaw) <= 15.0
        session.record_frame(FrameRecord(
            timestamp_ms=int(t * 1000),
            frame_index=index,
            face_detected=True,
            head_pitch=0.0,
            head_yaw=yaw,
            head_roll=roll_deg * math.sin(2 * math.pi * t / sweep_period_s),
            left_iris_offset=[offset, 0.0],
            right_iris_offset=[offset + horizontal_disparity, vertical_disparity],
            landmark_confidence=1.0,
            left_eye_aperture=left_aperture if with_apertures else None,
            right_eye_aperture=right_aperture if with_apertures else None,
            mouth_corner_asymmetry=(
                face_asymmetry if (with_symmetry and near_frontal) else None
            ),
            brow_height_asymmetry=0.0 if (with_symmetry and near_frontal) else None,
        ))

    return session.end_session(symptom_score=symptom_score)


def panel_for(**kwargs):
    return enrich_session(build_session(**kwargs))["screening_indications"]


def entry(panel, indication_id):
    matches = [e for e in panel["panel"] if e["id"] == indication_id]
    assert len(matches) == 1, f"{indication_id} appears {len(matches)} times"
    return matches[0]


def finding(panel, indication_id):
    return entry(panel, indication_id)["finding"]


# ---- metrics helpers ------------------------------------------------------

def test_moving_average_does_not_drag_the_ends_toward_zero():
    """The old mode='same' convolution corrupted the first and last samples.

    This is the regression that motivated the rewrite: a session starting at -40
    degrees had its opening samples pulled toward -24, which shrank yaw_range_deg
    and moved the first turning point.
    """
    values = np.full(50, -40.0)
    smoothed = metrics.moving_average(values, 5)
    assert smoothed.size == values.size, smoothed.size
    assert abs(smoothed[0] - (-40.0)) < 1e-9, smoothed[0]
    assert abs(smoothed[-1] - (-40.0)) < 1e-9, smoothed[-1]


def test_moving_average_still_smooths():
    values = np.array([0.0, 10.0] * 25)
    smoothed = metrics.moving_average(values, 5)
    assert np.std(smoothed) < np.std(values), (np.std(smoothed), np.std(values))


def test_dominant_frequency_finds_an_injected_sine():
    times = np.arange(0, 10, 1 / 30.0)
    values = 2.0 * np.sin(2 * math.pi * 4.0 * times)
    found = metrics.dominant_frequency(values, times, (2.5, 6.0))
    assert found.frequency_hz is not None and abs(found.frequency_hz - 4.0) < 0.2, (
        found.frequency_hz
    )
    assert found.rhythmicity > 0.9, found.rhythmicity
    # RMS of a 2.0 amplitude sine is 2/sqrt(2).
    assert abs(found.amplitude_rms - 2.0 / math.sqrt(2)) < 0.1, found.amplitude_rms


def test_dominant_frequency_amplitude_ignores_out_of_band_energy():
    """The reason the amplitude is not the standard deviation of the input.

    A large slow signal plus a small fast one must report the amplitude of the fast
    one. Reading the overall standard deviation instead is what reported a
    2 degree head tremor on a perfectly smooth head sweep.
    """
    times = np.arange(0, 12, 1 / 30.0)
    slow = 40.0 * np.sin(2 * math.pi * 0.33 * times)
    fast = 0.5 * np.sin(2 * math.pi * 4.0 * times)
    found = metrics.dominant_frequency(slow + fast, times, (2.5, 6.0))
    assert abs(found.frequency_hz - 4.0) < 0.2, found.frequency_hz
    assert found.amplitude_rms < 1.0, found.amplitude_rms
    assert found.amplitude_rms > 0.2, found.amplitude_rms


def test_dominant_frequency_refuses_a_band_above_nyquist():
    times = np.arange(0, 10, 1 / 10.0)          # 10 fps
    values = np.sin(2 * math.pi * 3.0 * times)
    found = metrics.dominant_frequency(values, times, (2.5, 6.0))
    assert found.frequency_hz is None, found.frequency_hz
    assert found.sample_rate_hz is not None, "the sample rate must still be reported"


# ---- facial symmetry geometry --------------------------------------------

def _symmetric_face(mouth_drop_left=0.0):
    """Minimal landmark array with the points facial_symmetry() reads."""
    pts = np.zeros((478, 3), dtype=float)
    pts[LM.LEFT_EYE_OUTER] = [0.30, 0.40, 0.0]
    pts[LM.RIGHT_EYE_OUTER] = [0.70, 0.40, 0.0]
    pts[LM.LEFT_EYE_TOP] = [0.38, 0.38, 0.0]
    pts[LM.RIGHT_EYE_TOP] = [0.62, 0.38, 0.0]
    pts[LM.LEFT_BROW_PEAK] = [0.38, 0.32, 0.0]
    pts[LM.RIGHT_BROW_PEAK] = [0.62, 0.32, 0.0]
    # Image y grows downward, so a lower mouth corner has a LARGER y.
    pts[LM.LEFT_MOUTH_CORNER] = [0.42, 0.70 + mouth_drop_left, 0.0]
    pts[LM.RIGHT_MOUTH_CORNER] = [0.58, 0.70, 0.0]
    pts[LM.FOREHEAD] = [0.50, 0.20, 0.0]
    pts[LM.CHIN] = [0.50, 0.85, 0.0]
    return pts


def test_symmetric_face_measures_near_zero():
    mouth, brow = facial_symmetry(_symmetric_face(), head_yaw=0.0)
    assert abs(mouth) < 1e-9, mouth
    assert abs(brow) < 1e-9, brow


def test_dropped_corner_is_detected_and_signed():
    mouth, _ = facial_symmetry(_symmetric_face(mouth_drop_left=0.04), head_yaw=0.0)
    # The dropped side is lower, so its height in the face frame is smaller.
    assert mouth < -0.05, mouth


def test_symmetry_survives_head_roll():
    """A tilted head must not read as a drooping face.

    This is the whole reason the measurement happens in a face-local frame rather
    than in image coordinates.
    """
    pts = _symmetric_face()
    angle = math.radians(20.0)
    rotation = np.array([
        [math.cos(angle), -math.sin(angle)],
        [math.sin(angle), math.cos(angle)],
    ])
    tilted = pts.copy()
    tilted[:, :2] = (pts[:, :2] - [0.5, 0.5]) @ rotation.T + [0.5, 0.5]
    mouth, _ = facial_symmetry(tilted, head_yaw=0.0)
    assert abs(mouth) < 1e-6, mouth


def test_symmetry_is_not_measured_off_frontal():
    mouth, brow = facial_symmetry(_symmetric_face(), head_yaw=45.0)
    assert mouth is None and brow is None, (mouth, brow)


# ---- signal blocks -------------------------------------------------------

def test_blinks_are_counted_as_events_not_frames():
    """A four-frame blink is one blink, not four."""
    result = build_session(duration_s=25.0, blink_every_s=5.0, blink_frames=4)
    block = result["oculomotor_signals"]
    assert block["blink_count"] == 5, block["blink_count"]
    assert 10 < block["blink_rate_per_min"] < 14, block["blink_rate_per_min"]


def test_blink_rate_is_absent_without_aperture_data():
    """Older captures have no aperture field, and must not report a rate of zero."""
    result = build_session(with_apertures=False)
    assert result["oculomotor_signals"]["blink_rate_per_min"] is None


def test_direction_split_needs_both_directions():
    block = signals.head_control(
        np.arange(0, 5, 0.1), np.zeros(50), np.zeros(50),
        np.zeros(50, dtype=bool), [], {},
    )
    assert block["insufficient_data"] is True
    assert block["direction_asymmetry_index"] is None


def test_clean_session_is_directionally_symmetric():
    block = build_session()["head_control"]
    assert block["direction_asymmetry_index"] < 0.15, (
        block["direction_asymmetry_index"]
    )


def test_one_sided_instability_shows_as_asymmetry():
    block = build_session(direction_penalty=0.02)["head_control"]
    assert block["direction_asymmetry_index"] > 0.30, (
        block["direction_asymmetry_index"]
    )


def test_off_axis_coupling_reflects_roll():
    flat = build_session(roll_deg=0.0)["head_control"]
    tilted = build_session(roll_deg=40.0)["head_control"]
    assert flat["off_axis_coupling_ratio"] < 0.05, flat["off_axis_coupling_ratio"]
    assert tilted["off_axis_coupling_ratio"] > 0.4, tilted["off_axis_coupling_ratio"]


def test_smooth_sweep_reports_no_meaningful_tremor():
    """The regression that the peak-band amplitude fix exists for."""
    block = build_session(tremor_deg=0.0)["head_control"]
    assert block["tremor_amplitude_deg"] < 0.5, block["tremor_amplitude_deg"]


def test_injected_tremor_is_measured_at_the_right_size():
    block = build_session(tremor_deg=2.0, tremor_hz=4.0)["head_control"]
    assert abs(block["tremor_frequency_hz"] - 4.0) < 0.3, block["tremor_frequency_hz"]
    # Peak to peak of a 2.0 amplitude sine is 4.0 degrees.
    assert 3.0 < block["tremor_amplitude_deg"] < 5.0, block["tremor_amplitude_deg"]


def test_eyelid_asymmetry_is_measured_against_the_mean():
    block = build_session(lid_ratio=0.7)["eyelid_signals"]
    # 0.30 against 0.21 is a 0.09 difference over a 0.255 mean.
    assert abs(block["aperture_asymmetry_ratio"] - 0.09 / 0.255) < 0.02, (
        block["aperture_asymmetry_ratio"]
    )


def test_asymmetry_alone_does_not_read_as_fatigue():
    """Cross-talk check: an uneven pair of lids that never changes is not fatigue."""
    block = build_session(duration_s=30.0, lid_ratio=0.7)["eyelid_signals"]
    assert abs(block["aperture_relative_decline"]) < 0.05, (
        block["aperture_relative_decline"]
    )


def test_fatigue_alone_does_not_read_as_asymmetry():
    block = build_session(duration_s=30.0, lid_decline=0.4)["eyelid_signals"]
    assert block["aperture_asymmetry_ratio"] < 0.05, (
        block["aperture_asymmetry_ratio"]
    )


def test_fatigable_droop_needs_a_long_enough_session():
    short = build_session(duration_s=12.0, lid_decline=0.4)["eyelid_signals"]
    assert short["aperture_relative_decline"] is None, (
        "a 12 second capture cannot support a fatigue comparison"
    )


def test_declining_aperture_is_measured():
    block = build_session(duration_s=30.0, lid_decline=0.4)["eyelid_signals"]
    # Both lids fall linearly to 60% of their starting opening, and the comparison
    # is between the middles of the first and last thirds, not the endpoints.
    assert 0.2 < block["aperture_relative_decline"] < 0.35, (
        block["aperture_relative_decline"]
    )


def test_alignment_disparity_is_signed_and_bias_free_in_std():
    block = build_session(horizontal_disparity=0.06)["ocular_alignment"]
    assert abs(block["horizontal_disparity_mean_offset_units"] - 0.06) < 0.005, (
        block["horizontal_disparity_mean_offset_units"]
    )
    # A constant offset adds nothing to the variability.
    assert block["horizontal_disparity_std_offset_units"] < 1e-6


# ---- the panel -----------------------------------------------------------

def test_panel_runs_every_check():
    panel = panel_for()
    assert panel["checks_run"] == len(indications.CHECKS)
    assert len(panel["panel"]) == len(indications.CHECKS)
    ids = [e["id"] for e in panel["panel"]]
    assert len(set(ids)) == len(ids), f"duplicate indication ids: {ids}"


def test_clean_session_flags_nothing():
    """The single most important test here.

    A panel that fires on a well-performed capture is worse than no panel: it
    trains the reader to ignore all of it.
    """
    panel = panel_for()
    assert panel["indicated"] == [], panel["indicated"]


def test_every_entry_carries_its_threshold_and_basis():
    for entry_dict in panel_for()["panel"]:
        assert entry_dict["screens_for"] or entry_dict["id"] == "unknown", entry_dict["id"]
        assert entry_dict["evidence_basis"] in (
            indications.BASIS_PUBLISHED_SIGN, indications.BASIS_BESPOKE_METRIC
        ), entry_dict
        if entry_dict["finding"] == indications.FINDING_INDICATED:
            assert entry_dict["thresholds"], entry_dict["id"]
            assert entry_dict["measured"], entry_dict["id"]
            assert entry_dict["caveat"], entry_dict["id"]
            assert entry_dict["next_step"], entry_dict["id"]


def test_not_assessable_always_explains_itself():
    """A silent not_assessable is indistinguishable from a bug."""
    for entry_dict in panel_for(with_apertures=False, with_symmetry=False)["panel"]:
        if entry_dict["finding"] == indications.FINDING_NOT_ASSESSABLE:
            assert entry_dict["reason"], entry_dict["id"]


def test_missing_signals_are_not_assessable_rather_than_negative():
    """The load-bearing safety property of the whole module.

    With no aperture data recorded, the eyelid and blink checks must not report
    "not indicated", which a reader would take as "your eyelids are fine".
    """
    panel = panel_for(with_apertures=False, with_symmetry=False)
    for indication_id in ("eyelid_asymmetry", "fatigable_eyelid_droop",
                          "blink_rate_abnormality", "facial_asymmetry"):
        assert finding(panel, indication_id) == indications.FINDING_NOT_ASSESSABLE, (
            indication_id, entry(panel, indication_id)
        )


def test_empty_session_yields_a_full_not_assessable_panel():
    panel = indications.assess({}, {})
    assert panel["checks_run"] == len(indications.CHECKS)
    assert panel["indicated"] == []
    assert len(panel["not_assessable"]) == len(indications.CHECKS)


def test_assess_never_raises_on_garbage():
    for garbage in (None, [], 0, "session", {"gaze_stability": "nope"},
                    {"head_control": []}, {"tracking_quality": {"face_detection_rate": "x"}}):
        panel = indications.assess(garbage, garbage)
        assert panel["checks_run"] == len(indications.CHECKS), garbage


def test_nystagmus_is_flagged():
    panel = panel_for(nystagmus_amplitude=0.03, nystagmus_hz=3.0)
    assert finding(panel, "rhythmic_eye_oscillation") == indications.FINDING_INDICATED, (
        entry(panel, "rhythmic_eye_oscillation")
    )


def test_head_tremor_does_not_masquerade_as_nystagmus():
    """A head oscillating at 4 Hz drives the eyes at 4 Hz. That is compensation.

    Without the cross-check, the eye channel picks the head tremor up and reports it
    as an independent involuntary eye movement, which is the same finding counted
    twice under two different condition names.
    """
    # Large enough that the eye channel's own amplitude threshold is cleared, so
    # the cross-check is what suppresses it rather than the size gate.
    panel = panel_for(tremor_deg=9.0, tremor_hz=4.0)
    assert finding(panel, "head_tremor") == indications.FINDING_INDICATED, (
        entry(panel, "head_tremor")
    )
    eye = entry(panel, "rhythmic_eye_oscillation")
    assert eye["measured"]["oscillation_amplitude_offset_units"] >= (
        indications.OSCILLATION_AMPLITUDE_OFFSET_UNITS
    ), "the eye channel must be over its own threshold for this test to mean anything"
    assert eye["finding"] == indications.FINDING_NOT_INDICATED, eye
    assert "matching_head_tremor_hz" in eye["measured"], eye["measured"]


def test_vertical_misalignment_is_flagged_and_marked_urgent():
    panel = panel_for(vertical_disparity=0.05)
    found = entry(panel, "vertical_ocular_misalignment")
    assert found["finding"] == indications.FINDING_INDICATED, found
    assert found["urgency"] == indications.URGENCY_EMERGENCY_IF_NEW, found["urgency"]
    assert panel["highest_urgency"] == indications.URGENCY_EMERGENCY_IF_NEW


def test_horizontal_misalignment_is_not_marked_urgent():
    """Horizontal deviation is not the central sign that vertical deviation is."""
    panel = panel_for(horizontal_disparity=0.08)
    found = entry(panel, "horizontal_ocular_misalignment")
    assert found["finding"] == indications.FINDING_INDICATED, found
    assert found["urgency"] == indications.URGENCY_ROUTINE, found["urgency"]


def test_facial_asymmetry_is_flagged_and_marked_urgent():
    panel = panel_for(face_asymmetry=0.05)
    found = entry(panel, "facial_asymmetry")
    assert found["finding"] == indications.FINDING_INDICATED, found
    assert found["urgency"] == indications.URGENCY_EMERGENCY_IF_NEW


def test_ptosis_is_flagged():
    panel = panel_for(lid_ratio=0.65)
    assert finding(panel, "eyelid_asymmetry") == indications.FINDING_INDICATED, (
        entry(panel, "eyelid_asymmetry")
    )


def test_fatigable_droop_is_flagged():
    panel = panel_for(duration_s=30.0, lid_decline=0.4)
    assert finding(panel, "fatigable_eyelid_droop") == indications.FINDING_INDICATED


def test_low_blink_rate_is_flagged():
    panel = panel_for(duration_s=30.0, blink_every_s=30.0)
    found = entry(panel, "blink_rate_abnormality")
    assert found["finding"] == indications.FINDING_INDICATED, found
    assert found["measured"]["blink_rate_per_min"] < indications.BLINK_RATE_LOW


def test_high_blink_rate_is_flagged():
    panel = panel_for(blink_every_s=1.2, blink_frames=3)
    found = entry(panel, "blink_rate_abnormality")
    assert found["finding"] == indications.FINDING_INDICATED, found
    assert found["measured"]["blink_rate_per_min"] > indications.BLINK_RATE_HIGH


def test_one_sided_gaze_instability_is_flagged():
    panel = panel_for(direction_penalty=0.02)
    assert finding(panel, "vestibular_asymmetry") == indications.FINDING_INDICATED, (
        entry(panel, "vestibular_asymmetry")
    )


def test_ambiguous_rotation_range_is_not_assessable():
    """Between the two yaw bounds, the tracker and the neck cannot be told apart.

    Before this distinction existed, the cervical check fired on essentially every
    capture, because a webcam session rarely reaches the protocol's 160 degrees.
    """
    panel = panel_for(sweep_amplitude_deg=40.0)      # 80 degrees total
    assert finding(panel, "cervical_rotation_restriction") == (
        indications.FINDING_NOT_ASSESSABLE
    ), entry(panel, "cervical_rotation_restriction")


def test_generous_rotation_range_is_not_indicated():
    panel = panel_for(sweep_amplitude_deg=60.0)      # 120 degrees total
    assert finding(panel, "cervical_rotation_restriction") == (
        indications.FINDING_NOT_INDICATED
    )


def test_severely_restricted_rotation_is_flagged():
    panel = panel_for(sweep_amplitude_deg=20.0)      # 40 degrees total
    assert finding(panel, "cervical_rotation_restriction") == (
        indications.FINDING_INDICATED
    ), entry(panel, "cervical_rotation_restriction")


def test_slow_capture_cannot_assess_frequency_signals():
    """A 12 fps capture must decline the frequency checks, not pass them."""
    panel = panel_for(fps=12.0, duration_s=30.0, nystagmus_amplitude=0.03)
    for indication_id in ("rhythmic_eye_oscillation", "head_tremor"):
        found = entry(panel, indication_id)
        assert found["finding"] == indications.FINDING_NOT_ASSESSABLE, (
            indication_id, found
        )
        assert "per second" in (found["reason"] or ""), found["reason"]
        assert found["measured"]["sample_rate_hz"] < indications.MIN_FPS_FOR_FREQUENCY


def test_poor_tracking_downgrades_findings_to_not_assessable():
    """A recording too intermittent to characterise anything must not report signs."""
    session = build_session(face_asymmetry=0.05)
    session["tracking_quality"]["face_detection_rate"] = 0.4
    panel = indications.assess(session, session.get("screening_summary") or {})
    assert panel["tracking_sufficient"] is False
    assert panel["indicated"] == [], panel["indicated"]
    found = [e for e in panel["panel"] if e["id"] == "facial_asymmetry"][0]
    assert found["finding"] == indications.FINDING_NOT_ASSESSABLE
    # The number is still reported, so the downgrade is visible rather than a hole.
    assert found["measured"].get("mouth_corner_asymmetry") is not None


def test_urgency_is_cleared_when_not_indicated():
    """Only an indicated entry may carry an elevated urgency."""
    for entry_dict in panel_for()["panel"]:
        if entry_dict["finding"] != indications.FINDING_INDICATED:
            assert entry_dict["urgency"] == indications.URGENCY_ROUTINE, entry_dict["id"]


def test_no_finding_summary_is_not_a_clearance():
    """Wording check, and it is load bearing rather than cosmetic.

    A panel with nothing flagged is the moment a reader is most likely to conclude
    that the person is fine, which this tool cannot support.
    """
    panel = panel_for()
    assert "not a clearance" in panel["summary"].lower(), panel["summary"]
    assert "not a clearance" in panel["method"]["what_not_indicated_means"].lower()


def test_emergency_note_is_always_present():
    panel = panel_for()
    assert "emergency" in panel["emergency_note"].lower()
    assert "cannot triage" in panel["emergency_note"].lower()


def test_vms_indication_tracks_the_screening_tier():
    high = enrich_session(build_session(symptom_score=9))
    found = [
        e for e in high["screening_indications"]["panel"]
        if e["id"] == "visual_motion_sensitivity"
    ][0]
    assert found["finding"] == indications.FINDING_INDICATED, found
    assert found["measured"]["severity_tier"] == high["screening_summary"]["severity_tier"]


def test_a_broken_check_does_not_take_down_the_panel():
    """A new indication with a bug must not be able to hide the VOMS result."""
    def exploding(session, summary):
        raise RuntimeError("deliberate")

    original = indications.CHECKS
    indications.CHECKS = original + (exploding,)
    try:
        panel = indications.assess({}, {})
    finally:
        indications.CHECKS = original

    assert panel["checks_run"] == len(original) + 1
    broken = [e for e in panel["panel"] if "deliberate" in (e["reason"] or "")]
    assert len(broken) == 1, panel["not_assessable"]


def test_enrich_session_attaches_the_panel_without_disturbing_the_summary():
    raw = build_session()
    enriched = enrich_session(raw)
    assert "screening_indications" in enriched
    assert "screening_summary" in enriched
    # The original capture is untouched, which score_session.py depends on.
    assert "screening_indications" not in raw


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
