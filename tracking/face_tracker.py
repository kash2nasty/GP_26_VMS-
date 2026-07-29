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
    left_iris_offset: list | None   # [horizontal, vertical], eye-socket-normalized
    right_iris_offset: list | None
    landmark_confidence: float | None

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


def _iris_offset(pts, iris_idx, outer_idx, inner_idx, top_idx, bottom_idx):
    """Iris center offset inside its own eye socket, in socket-relative units.

    Builds a local 2D frame from the eye corners so the measurement rotates with
    the head instead of with the camera. Returns [horizontal, vertical] where 0,0
    means the iris sits at the socket center; roughly +/-0.5 spans the socket.
    Positive horizontal = toward the outer (temple) corner.
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
    return [float(np.dot(d, axis_u) / width), float(np.dot(d, perp_u) / height)]


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
            left = _iris_offset(
                pts, LM.LEFT_IRIS_CENTER, LM.LEFT_EYE_OUTER, LM.LEFT_EYE_INNER,
                LM.LEFT_EYE_TOP, LM.LEFT_EYE_BOTTOM,
            )
            right = _iris_offset(
                pts, LM.RIGHT_IRIS_CENTER, LM.RIGHT_EYE_OUTER, LM.RIGHT_EYE_INNER,
                LM.RIGHT_EYE_TOP, LM.RIGHT_EYE_BOTTOM,
            )

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
        )

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
