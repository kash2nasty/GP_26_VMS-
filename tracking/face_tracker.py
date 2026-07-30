"""Per-frame face tracking: head pose (pitch/yaw/roll) + iris offset within the eye socket."""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

from . import landmarks as LM

DEFAULT_MODEL_PATH = "models/face_landmarker.task"


@dataclass
class FrameRecord:
    """One structured observation per processed frame."""
    timestamp_ms: int
    frame_index: int
    face_detected: bool
    head_pitch: float | None       # degrees, + = looking up
    head_yaw: float | None         # degrees, + = turning to subject's left
    head_roll: float | None        # degrees, + = tilting to subject's right
    left_iris_offset: list | None   # [horizontal, vertical], eye-socket-normalized.
    right_iris_offset: list | None  # horizontal: + = toward subject's right, both eyes.
    landmark_confidence: float | None
    # Vertical eye opening / eye width. Open eye ~0.25-0.40, collapses toward 0
    # during a blink. Default None so callers predating this field still work.
    left_eye_aperture: float | None = None
    right_eye_aperture: float | None = None
    # Resting facial symmetry, in face-width units, measured in a head-roll
    # corrected face frame. Positive means the landmarks.py "left" side sits
    # higher. None when the face was too far from frontal to measure.
    mouth_corner_asymmetry: float | None = None
    brow_height_asymmetry: float | None = None

    def to_dict(self):
        return asdict(self)


def _euler_from_matrix(matrix: np.ndarray) -> tuple[float, float, float]:
    """Decompose MediaPipe's 4x4 facial transformation matrix into pitch/yaw/roll degrees."""
    r = np.asarray(matrix, dtype=float)[:3, :3]
    sy = math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)
    if sy > 1e-6:
        pitch = math.atan2(r[2, 1], r[2, 2])
        yaw = math.atan2(-r[2, 0], sy)
        roll = math.atan2(r[1, 0], r[0, 0])
    else:
        pitch = math.atan2(-r[1, 2], r[1, 1])
        yaw = math.atan2(-r[2, 0], sy)
        roll = 0.0
    return math.degrees(pitch), math.degrees(yaw), math.degrees(roll)


def _iris_offset(pts, iris_idx, outer_idx, inner_idx, top_idx, bottom_idx, lateral_sign):
    """Iris center offset inside its own eye socket, in socket-relative units.

    Builds a local 2D frame from the eye corners so the measurement rotates with
    the head instead of with the camera. Returns [horizontal, vertical] where 0,0
    means the iris sits at the socket center; roughly +/-0.5 spans the socket.

    lateral_sign flips the horizontal axis so positive means "toward the
    subject's right" for BOTH eyes. Without this, the left eye's "outer"
    corner is on the subject's left while the right eye's "outer" corner is on
    the subject's right, so during VOR (both eyes rotating the same real-world
    direction to compensate for head yaw) the two eyes' raw offsets would carry
    opposite signs and cancel when averaged together.
    """
    iris = pts[iris_idx][:2]
    outer = pts[outer_idx][:2]
    inner = pts[inner_idx][:2]
    top = pts[top_idx][:2]
    bottom = pts[bottom_idx][:2]

    axis = outer - inner
    width = np.linalg.norm(axis)
    if width < 1e-6:
        return None
    axis_u = axis / width

    # Perpendicular in-plane axis, oriented so "up" in the socket is positive.
    perp_u = np.array([-axis_u[1], axis_u[0]])
    if np.dot(perp_u, top - bottom) < 0:
        perp_u = -perp_u

    socket_center = (outer + inner) / 2.0
    height = abs(np.dot(top - bottom, perp_u))
    if height < 1e-6:
        height = width * 0.5  # squinting/blink guard

    d = iris - socket_center
    horizontal = (np.dot(d, axis_u) / width) * lateral_sign
    return [float(horizontal), float(np.dot(d, perp_u) / height)]


# The two eyes' outer (temple) corners sit on opposite sides of the face midline,
# so measuring each eye toward its own outer corner gives the eyes OPPOSING signs
# during VOR -- where both eyes rotate the same real-world direction to
# compensate for head yaw. The session layer averages the eyes together, so that
# cancels the physiological signal and collapses compensation_r2. These signs
# normalize both eyes onto one shared real-world direction. Keep this as the
# single source of truth for the convention; tests/test_gaze_sign.py pins it.
_LEFT_LATERAL_SIGN = -1.0
_RIGHT_LATERAL_SIGN = 1.0


def _eye_aperture(pts, outer_idx, inner_idx, top_idx, bottom_idx):
    """Vertical eye opening as a fraction of eye width -- a blink detector.

    An eye-aspect-ratio style measure. An open eye sits around 0.25-0.40; during a
    blink it collapses toward 0. Normalising by eye width makes it invariant to
    how far the subject sits from the camera.

    This exists because _iris_offset() cannot distinguish a blink from a genuine
    gaze deviation: with the lids shut the iris landmarks are unreliable and can
    report a large spurious offset, which inflates residual_rms and therefore the
    screening tier. Rejection happens in voms_session, using this value.
    """
    outer = pts[outer_idx][:2]
    inner = pts[inner_idx][:2]
    top = pts[top_idx][:2]
    bottom = pts[bottom_idx][:2]

    width = float(np.linalg.norm(outer - inner))
    if width < 1e-6:
        return None
    return float(np.linalg.norm(top - bottom) / width)


def both_eye_apertures(pts):
    """Per-eye aperture ratios as (left, right); either may be None."""
    left = _eye_aperture(
        pts, LM.LEFT_EYE_OUTER, LM.LEFT_EYE_INNER,
        LM.LEFT_EYE_TOP, LM.LEFT_EYE_BOTTOM,
    )
    right = _eye_aperture(
        pts, LM.RIGHT_EYE_OUTER, LM.RIGHT_EYE_INNER,
        LM.RIGHT_EYE_TOP, LM.RIGHT_EYE_BOTTOM,
    )
    return left, right


# Beyond this much head yaw the face is turned far enough that perspective
# foreshortening dominates any real left/right difference, so symmetry is not
# measured at all rather than measured badly.
MAX_YAW_FOR_SYMMETRY_DEG = 15.0


def _face_frame(pts):
    """Build a head-roll corrected 2D face frame from the outer eye corners.

    Returns (axis_u, perp_u, width) where axis_u runs between the outer eye
    corners, perp_u points toward the forehead, and width is the inter-canthal
    distance used to normalise every measurement. Working in this frame is what
    makes the symmetry numbers survive head tilt: a tilted head moves both mouth
    corners in image space but leaves their heights within the face unchanged.
    """
    left = pts[LM.LEFT_EYE_OUTER][:2]
    right = pts[LM.RIGHT_EYE_OUTER][:2]
    axis = right - left
    width = float(np.linalg.norm(axis))
    if width < 1e-6:
        return None
    axis_u = axis / width

    perp_u = np.array([-axis_u[1], axis_u[0]])
    # Orient toward the forehead, whichever way the cross product landed.
    if np.dot(perp_u, pts[LM.FOREHEAD][:2] - pts[LM.CHIN][:2]) < 0:
        perp_u = -perp_u
    return axis_u, perp_u, width


def facial_symmetry(pts, head_yaw):
    """Resting left/right height difference of the mouth corners and brows.

    Returns (mouth_corner_asymmetry, brow_height_asymmetry) in face-width units,
    or (None, None) when the head was too far from frontal to trust.

    WHY HEIGHTS AND NOT DISTANCES
        A drooping side of the face shows up as one mouth corner sitting lower
        than the other and one brow sitting lower than the other. Horizontal
        distances from the midline change with yaw even on a perfectly symmetric
        face, whereas heights measured in the face frame do not, so heights are
        the measurement that survives a subject who is not perfectly square to
        the camera.

    WHY THE SIGN IS ONLY ADVISORY
        See LM.ANATOMICAL_SIDE_CAVEAT. The magnitude is measured; which side of
        the person it belongs to has not been verified in this project.
    """
    if head_yaw is not None and abs(head_yaw) > MAX_YAW_FOR_SYMMETRY_DEG:
        return None, None

    frame = _face_frame(pts)
    if frame is None:
        return None, None
    _, perp_u, width = frame

    def height(index):
        return float(np.dot(pts[index][:2], perp_u)) / width

    mouth = height(LM.LEFT_MOUTH_CORNER) - height(LM.RIGHT_MOUTH_CORNER)
    # Brow peaks are compared relative to their own eye, so a naturally uneven
    # brow line matters less than a brow that has moved away from its eye.
    brow = (
        (height(LM.LEFT_BROW_PEAK) - height(LM.LEFT_EYE_TOP))
        - (height(LM.RIGHT_BROW_PEAK) - height(LM.RIGHT_EYE_TOP))
    )
    return float(mouth), float(brow)


def both_iris_offsets(pts):
    """Per-eye [horizontal, vertical] iris offsets in a shared sign convention.

    Returns (left, right); either may be None if that eye's geometry was
    degenerate. Positive horizontal means the same real-world direction for both
    eyes, which is what makes averaging them valid downstream.
    """
    left = _iris_offset(
        pts, LM.LEFT_IRIS_CENTER, LM.LEFT_EYE_OUTER, LM.LEFT_EYE_INNER,
        LM.LEFT_EYE_TOP, LM.LEFT_EYE_BOTTOM, lateral_sign=_LEFT_LATERAL_SIGN,
    )
    right = _iris_offset(
        pts, LM.RIGHT_IRIS_CENTER, LM.RIGHT_EYE_OUTER, LM.RIGHT_EYE_INNER,
        LM.RIGHT_EYE_TOP, LM.RIGHT_EYE_BOTTOM, lateral_sign=_RIGHT_LATERAL_SIGN,
    )
    return left, right


class FaceTracker:
    """Wraps MediaPipe Face Landmarker and turns each frame into a FrameRecord."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, num_faces: int = 1):
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.VIDEO,
            num_faces=num_faces,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)

    def process(self, image_bgr: np.ndarray, timestamp_ms: int, frame_index: int) -> FrameRecord:
        rgb = image_bgr[:, :, ::-1].copy()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.face_landmarks:
            return FrameRecord(
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
                face_detected=False,
                head_pitch=None,
                head_yaw=None,
                head_roll=None,
                left_iris_offset=None,
                right_iris_offset=None,
                landmark_confidence=None,
            )

        face = result.face_landmarks[0]
        pts = np.array([[p.x, p.y, p.z] for p in face], dtype=float)

        if result.facial_transformation_matrixes:
            pitch, yaw, roll = _euler_from_matrix(result.facial_transformation_matrixes[0])
        else:
            pitch = yaw = roll = None

        has_iris = len(face) > LM.RIGHT_IRIS_CENTER
        left = right = None
        if has_iris:
            left, right = both_iris_offsets(pts)
        left_aperture, right_aperture = both_eye_apertures(pts)
        mouth_asymmetry, brow_asymmetry = facial_symmetry(pts, yaw)

        # The Tasks API exposes no per-face score here, so we report presence-based
        # confidence: the fraction of landmarks that fall inside the frame bounds.
        in_bounds = np.mean(
            (pts[:, 0] >= 0) & (pts[:, 0] <= 1) & (pts[:, 1] >= 0) & (pts[:, 1] <= 1)
        )

        return FrameRecord(
            timestamp_ms=timestamp_ms,
            frame_index=frame_index,
            face_detected=True,
            head_pitch=pitch,
            head_yaw=yaw,
            head_roll=roll,
            left_iris_offset=left,
            right_iris_offset=right,
            landmark_confidence=float(in_bounds),
            left_eye_aperture=left_aperture,
            right_eye_aperture=right_aperture,
            mouth_corner_asymmetry=mouth_asymmetry,
            brow_height_asymmetry=brow_asymmetry,
        )

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
