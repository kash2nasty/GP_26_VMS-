"""Regression tests for the left/right iris sign convention.

Run directly (no pytest needed):

    .venv\\Scripts\\activate
    python tests/test_gaze_sign.py

Background: the two eyes' "outer" (temple) corners sit on opposite sides of the
face midline. If each eye's horizontal iris offset is measured toward its own
outer corner, then during real VOR -- where both eyes rotate the SAME real-world
direction to compensate for head yaw -- the two eyes report opposite signs. The
session layer averages the two eyes together, so that cancels the physiological
signal to near zero and collapses compensation_r2. These tests pin the shared
"+ = one consistent real-world direction" convention that prevents it.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from session.metrics import gaze_stability                        # noqa: E402
from session.voms_session import SessionConfig, VOMSSession        # noqa: E402
from tracking import landmarks as LM                               # noqa: E402
from tracking.face_tracker import FrameRecord, both_iris_offsets   # noqa: E402


def _synthetic_eye_landmarks(iris_shift: float) -> np.ndarray:
    """Build a fake 478-landmark array with both eyes' irises shifted together.

    Geometry is mirrored about the midline (x=0.5): one eye's outer corner points
    toward -x, the other's toward +x, which is the anatomical fact that drives
    this whole bug. Both irises are then displaced by the same image-space
    `iris_shift`, i.e. both eyes looking the same real-world direction -- what
    VOR does during a head turn.

    Note: this deliberately does not assert which physical eye MediaPipe's
    LEFT_*/RIGHT_* constants refer to. The invariant under test is symmetric, so
    it holds either way round.
    """
    pts = np.zeros((478, 3), dtype=float)

    # Eye whose outer corner is at lower x.
    pts[LM.LEFT_EYE_OUTER] = [0.30, 0.50, 0.0]
    pts[LM.LEFT_EYE_INNER] = [0.40, 0.50, 0.0]
    pts[LM.LEFT_EYE_TOP] = [0.35, 0.48, 0.0]
    pts[LM.LEFT_EYE_BOTTOM] = [0.35, 0.52, 0.0]
    pts[LM.LEFT_IRIS_CENTER] = [0.35 + iris_shift, 0.50, 0.0]

    # Mirrored eye, outer corner at higher x.
    pts[LM.RIGHT_EYE_OUTER] = [0.70, 0.50, 0.0]
    pts[LM.RIGHT_EYE_INNER] = [0.60, 0.50, 0.0]
    pts[LM.RIGHT_EYE_TOP] = [0.65, 0.48, 0.0]
    pts[LM.RIGHT_EYE_BOTTOM] = [0.65, 0.52, 0.0]
    pts[LM.RIGHT_IRIS_CENTER] = [0.65 + iris_shift, 0.50, 0.0]

    return pts


def test_both_eyes_agree_in_sign():
    """Eyes looking the same real-world direction must report the same sign.

    Goes through both_iris_offsets() -- the production entry point that owns the
    sign convention -- rather than re-specifying the signs here, so flipping the
    convention in face_tracker.py actually fails this test.
    """
    for shift in (0.04, -0.04):
        left, right = both_iris_offsets(_synthetic_eye_landmarks(shift))
        assert left is not None and right is not None
        assert (left[0] > 0) == (right[0] > 0), (
            f"shift={shift}: eyes disagree in sign "
            f"(left={left[0]:+.4f}, right={right[0]:+.4f}) -- the averaged "
            "signal will cancel and compensation_r2 will collapse"
        )
        # Same magnitude too, given the geometry is a clean mirror image.
        assert math.isclose(left[0], right[0], abs_tol=1e-9)


def test_averaging_preserves_magnitude():
    """The session layer averages both eyes; that must not shrink the signal."""
    left, right = both_iris_offsets(_synthetic_eye_landmarks(0.04))
    averaged = (left[0] + right[0]) / 2.0
    assert abs(averaged) > 0.1, (
        f"averaged horizontal offset collapsed to {averaged:+.6f}; expected the "
        "two eyes to reinforce, not cancel"
    )


def test_zero_shift_is_centered():
    """An iris at the socket center reads ~0 regardless of the sign flip."""
    left, right = both_iris_offsets(_synthetic_eye_landmarks(0.0))
    assert math.isclose(left[0], 0.0, abs_tol=1e-9)
    assert math.isclose(right[0], 0.0, abs_tol=1e-9)


def _synthetic_vor_session(mirror_right_eye: bool) -> dict:
    """Run a full session over synthetic perfect-VOR frames.

    If mirror_right_eye is True the two eyes are given opposing signs, which
    reproduces the original bug end to end through the real averaging code.
    """
    fps = 30.0
    duration_s = 20.0
    amplitude_deg = 40.0
    period_s = 3.0
    vor_gain = -0.004  # offset units per degree of yaw, ~ what real runs show

    session = VOMSSession(config=SessionConfig(target_reps=99, max_duration_s=1e6))
    session.start_session()

    for i in range(int(fps * duration_s)):
        t = i / fps
        yaw = amplitude_deg * math.sin(2 * math.pi * t / period_s)
        offset = vor_gain * yaw
        right_offset = -offset if mirror_right_eye else offset
        session.record_frame(FrameRecord(
            timestamp_ms=int(t * 1000),
            frame_index=i,
            face_detected=True,
            head_pitch=0.0,
            head_yaw=yaw,
            head_roll=0.0,
            left_iris_offset=[offset, 0.0],
            right_iris_offset=[right_offset, 0.0],
            landmark_confidence=1.0,
        ))

    return session.end_session(symptom_score=None)


def test_perfect_vor_fits_cleanly():
    """Synthetic perfect compensation should fit with high r2 and low residual."""
    gaze = _synthetic_vor_session(mirror_right_eye=False)["gaze_stability"]
    assert not gaze["insufficient_data"]
    assert gaze["compensation_r2"] > 0.99, (
        f"perfect synthetic VOR only reached r2={gaze['compensation_r2']}"
    )
    assert gaze["residual_rms_offset_units"] < 0.005


def test_mirrored_eyes_would_destroy_the_signal():
    """Guards the bug itself: opposing per-eye signs must NOT look like good data.

    This is the shape the original bug produced -- near-zero fitted slope and
    collapsed r2 on data that is physiologically perfect.
    """
    gaze = _synthetic_vor_session(mirror_right_eye=True)["gaze_stability"]
    collapsed = (
        gaze["insufficient_data"]
        or gaze["compensation_r2"] is None
        or gaze["compensation_r2"] < 0.1
    )
    assert collapsed, (
        "mirrored per-eye signs still produced a confident fit "
        f"(r2={gaze['compensation_r2']}); this test can no longer detect the bug"
    )


def test_gaze_stability_needs_enough_moving_frames():
    """Fewer than 10 moving frames must report insufficient_data, not a fit."""
    yaw = np.linspace(-20.0, 20.0, 8)
    iris = -0.004 * yaw
    out = gaze_stability(yaw, iris, np.ones(8, dtype=bool))
    assert out["insufficient_data"]
    assert out["compensation_r2"] is None


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
