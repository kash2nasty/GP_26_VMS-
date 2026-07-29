"""Tests for blink rejection in the gaze-stability pipeline.

Run directly (no pytest needed):

    .venv\\Scripts\\activate
    python tests/test_blink_rejection.py

Background: during a blink the iris landmarks are unreliable and can report a
large spurious offset. _iris_offset() cannot tell that apart from a genuine gaze
deviation, so an unrejected blink inflates residual_rms -> lowers
fixation_stability_score -> raises the screening tier. A ~21 s capture at a normal
blink rate contains roughly 5-7 blinks, so this is the common case, not an edge
case.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from session.voms_session import SessionConfig, VOMSSession       # noqa: E402
from tracking import landmarks as LM                              # noqa: E402
from tracking.face_tracker import (                               # noqa: E402
    FrameRecord,
    both_eye_apertures,
)

OPEN_APERTURE = 0.30      # typical open eye
CLOSED_APERTURE = 0.04    # lids shut


def _landmarks_with_opening(vertical_gap: float) -> np.ndarray:
    """Synthetic 478-landmark array with a given eye opening, width fixed at 0.10."""
    pts = np.zeros((478, 3), dtype=float)
    half = vertical_gap / 2.0

    pts[LM.LEFT_EYE_OUTER] = [0.30, 0.50, 0.0]
    pts[LM.LEFT_EYE_INNER] = [0.40, 0.50, 0.0]
    pts[LM.LEFT_EYE_TOP] = [0.35, 0.50 - half, 0.0]
    pts[LM.LEFT_EYE_BOTTOM] = [0.35, 0.50 + half, 0.0]

    pts[LM.RIGHT_EYE_OUTER] = [0.70, 0.50, 0.0]
    pts[LM.RIGHT_EYE_INNER] = [0.60, 0.50, 0.0]
    pts[LM.RIGHT_EYE_TOP] = [0.65, 0.50 - half, 0.0]
    pts[LM.RIGHT_EYE_BOTTOM] = [0.65, 0.50 + half, 0.0]
    return pts


def test_aperture_is_opening_over_width():
    """Eye width is 0.10, so a 0.03 gap must read as 0.30."""
    left, right = both_eye_apertures(_landmarks_with_opening(0.03))
    assert math.isclose(left, 0.30, abs_tol=1e-9), left
    assert math.isclose(right, 0.30, abs_tol=1e-9), right


def test_aperture_collapses_when_lids_shut():
    left, right = both_eye_apertures(_landmarks_with_opening(0.002))
    assert left < 0.05, left
    assert right < 0.05, right


def test_aperture_is_invariant_to_distance_from_camera():
    """Scaling the whole face must not change the aperture ratio."""
    near = _landmarks_with_opening(0.03)
    far = near * 0.5          # same face, half the size in frame
    assert math.isclose(both_eye_apertures(near)[0],
                        both_eye_apertures(far)[0], abs_tol=1e-9)


def _run_session(blink_frames=(), blink_iris_offset=0.0, aperture=OPEN_APERTURE,
                 collapse_aperture=True):
    """Synthetic perfect-VOR session, optionally with blinks injected.

    blink_frames get a spurious iris offset -- the shape a real blink produces --
    and, when collapse_aperture is True, a collapsed aperture alongside it.
    Setting collapse_aperture=False injects the same artifact with the lids
    reported open, which is how the control case below shows that rejection is
    what suppresses it.
    """
    fps, duration_s = 30.0, 20.0
    amplitude_deg, period_s, vor_gain = 40.0, 3.0, -0.004

    session = VOMSSession(config=SessionConfig(target_reps=99, max_duration_s=1e6))
    session.start_session()

    for i in range(int(fps * duration_s)):
        t = i / fps
        yaw = amplitude_deg * math.sin(2 * math.pi * t / period_s)
        blinking = i in blink_frames
        offset = blink_iris_offset if blinking else vor_gain * yaw
        eye = CLOSED_APERTURE if (blinking and collapse_aperture) else aperture
        session.record_frame(FrameRecord(
            timestamp_ms=int(t * 1000),
            frame_index=i,
            face_detected=True,
            head_pitch=0.0,
            head_yaw=yaw,
            head_roll=0.0,
            left_iris_offset=[offset, 0.0],
            right_iris_offset=[offset, 0.0],
            landmark_confidence=1.0,
            left_eye_aperture=eye,
            right_eye_aperture=eye,
        ))
    return session.end_session(symptom_score=None)


def test_clean_session_excludes_nothing():
    result = _run_session()
    assert result["gaze_stability"]["frames_excluded_blink"] == 0
    assert result["gaze_stability"]["compensation_r2"] > 0.99


def test_blink_frames_are_excluded_from_the_fit():
    """Checks frames actually left the fit, not merely that a count was reported.

    An earlier version asserted only frames_excluded_blink > 0, which a mutation
    disabling the exclusion itself survived: the count was still computed while
    nothing was removed. moving_frames_analyzed is the number actually fitted, so
    it is the honest witness.
    """
    blinks = tuple(range(100, 106))
    clean = _run_session()["gaze_stability"]
    blinked = _run_session(
        blink_frames=blinks, blink_iris_offset=0.35,
    )["gaze_stability"]

    assert blinked["frames_excluded_blink"] == len(blinks), (
        blinked["frames_excluded_blink"]
    )
    # Every injected blink lands inside the moving window, so the fitted count
    # must drop by exactly that many frames.
    assert blinked["moving_frames_analyzed"] == (
        clean["moving_frames_analyzed"] - len(blinks)
    ), (clean["moving_frames_analyzed"], blinked["moving_frames_analyzed"])


def test_spurious_blink_offsets_do_not_inflate_the_residual():
    """The money test: a blink-sized artifact must not change the tier.

    Six frames carrying a 0.35-unit offset -- roughly what the real capture's
    residual_max showed -- would dominate residual_rms if admitted to the fit.
    """
    clean = _run_session()["gaze_stability"]
    with_blinks = _run_session(
        blink_frames=tuple(range(100, 106)), blink_iris_offset=0.35,
    )["gaze_stability"]

    assert with_blinks["residual_rms_offset_units"] < 0.005, (
        f"blink artifacts leaked into the fit: rms "
        f"{with_blinks['residual_rms_offset_units']} vs clean "
        f"{clean['residual_rms_offset_units']}"
    )
    assert with_blinks["compensation_r2"] > 0.99, with_blinks["compensation_r2"]
    assert with_blinks["fixation_stability_score"] > 90.0


def test_rejection_is_load_bearing():
    """Confirms the previous test would fail without rejection.

    Same artifacts, but with the aperture left open so nothing is rejected. If
    this does NOT blow up the residual, the money test above proves nothing.
    """
    unrejected = _run_session(
        blink_frames=tuple(range(100, 106)),
        blink_iris_offset=0.35,
        collapse_aperture=False,   # lids reported open despite the artifact
    )["gaze_stability"]
    # aperture stays open, so nothing is excluded...
    assert unrejected["frames_excluded_blink"] == 0
    # ...and the artifact does real damage.
    assert unrejected["residual_rms_offset_units"] > 0.02, (
        "injected artifact did not perturb the fit, so the rejection test is "
        f"not meaningful: rms {unrejected['residual_rms_offset_units']}"
    )


def test_blinks_do_not_affect_head_motion():
    """A blink disturbs the eyes, not head pose -- reps must be unchanged."""
    clean = _run_session()["head_motion"]
    blinked = _run_session(
        blink_frames=tuple(range(100, 106)), blink_iris_offset=0.35,
    )["head_motion"]
    assert clean["completed_reps"] == blinked["completed_reps"]
    assert clean["total_sweeps"] == blinked["total_sweeps"]
    assert clean["yaw_range_deg"] == blinked["yaw_range_deg"]


def test_missing_aperture_is_not_treated_as_a_blink():
    """Records predating the aperture field must still be scored, not dropped."""
    result = _run_session(aperture=None)
    assert result["gaze_stability"]["frames_excluded_blink"] == 0
    assert result["gaze_stability"]["insufficient_data"] is False
    assert result["gaze_stability"]["compensation_r2"] > 0.99


def test_threshold_is_reported_in_output():
    """Pins the threshold to a literal as well as checking it reaches the output.

    Comparing only against SessionConfig would be tautological -- both sides move
    together. The literal makes retuning this provisional value a deliberate act
    that shows up in a diff.
    """
    gaze = _run_session()["gaze_stability"]
    assert gaze["min_eye_aperture_ratio"] == 0.15, gaze["min_eye_aperture_ratio"]
    assert gaze["min_eye_aperture_ratio"] == SessionConfig().min_eye_aperture_ratio


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
