"""Frame source abstraction: live webcam or a video file, same interface either way."""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Frame:
    image_bgr: np.ndarray
    timestamp_ms: int
    index: int


class FrameSource:
    """Yields frames from a webcam index or a video file path.

    For a webcam, timestamps come from the wall clock and frames are throttled
    toward target_fps. For a video file, timestamps come from the file's own
    position so analysis is independent of how fast we can decode.
    """

    def __init__(
        self,
        source: int | str = 0,
        target_fps: float = 30.0,
        width: int | None = 1280,
        height: int | None = 720,
    ):
        self.source = source
        self.target_fps = target_fps
        self.is_file = isinstance(source, str)
        self._frame_interval = 1.0 / target_fps if target_fps > 0 else 0.0

        if self.is_file:
            self.cap = cv2.VideoCapture(source)
        else:
            # CAP_DSHOW avoids multi-second startup delays on Windows.
            self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, target_fps)

        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open frame source: {source!r}")

        self._index = 0
        self._start_wall = None
        self._last_emit = None
        self._last_timestamp_ms = -1

    def frames(self):
        """Generator of Frame objects until the source is exhausted or stopped."""
        self._start_wall = time.perf_counter()
        while True:
            if not self.is_file and self._frame_interval:
                now = time.perf_counter()
                if self._last_emit is not None:
                    sleep_for = self._frame_interval - (now - self._last_emit)
                    if sleep_for > 0:
                        time.sleep(sleep_for)

            ok, image = self.cap.read()
            if not ok:
                break

            if self.is_file:
                ts = self.cap.get(cv2.CAP_PROP_POS_MSEC)
                timestamp_ms = int(ts) if ts and ts > 0 else int(
                    self._index * 1000.0 / (self.cap.get(cv2.CAP_PROP_FPS) or self.target_fps)
                )
            else:
                timestamp_ms = int((time.perf_counter() - self._start_wall) * 1000)

            # MediaPipe VIDEO mode requires strictly increasing timestamps.
            if timestamp_ms <= self._last_timestamp_ms:
                timestamp_ms = self._last_timestamp_ms + 1
            self._last_timestamp_ms = timestamp_ms

            self._last_emit = time.perf_counter()
            frame = Frame(image_bgr=image, timestamp_ms=timestamp_ms, index=self._index)
            self._index += 1
            yield frame

    def release(self):
        if self.cap is not None:
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
