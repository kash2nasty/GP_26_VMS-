"""Browser-driven capture: the frontend streams frames, Python does the analysis.

WHY THE ANALYSIS STAYS IN PYTHON
    The obvious alternative is running MediaPipe in the browser with
    @mediapipe/tasks-vision and porting the metrics to TypeScript. That would mean
    a second implementation of the iris sign convention, blink rejection, sweep
    detection, the gaze fit and the scoring thresholds -- all of which are covered
    by a Python test suite that exists because a sign-convention bug in exactly
    that math silently destroyed the core signal once already. Two copies of it
    would reintroduce that class of bug with nothing to catch the drift. So the
    browser is a camera and a display; every number still comes from the
    validated pipeline.

WHY FRAMES AND NOT A VIDEO FILE
    Uploading a recording would be fewer messages, but MediaRecorder produces
    WebM/VP8-9 and OpenCV's Windows build cannot be relied on to decode it. JPEG
    frames go through cv2.imdecode, which is unconditionally supported, and they
    also allow live rep feedback during the test rather than only after it.

WHY MEDIAPIPE IS IMPORTED LAZILY
    Importing it at module scope would drag the entire camera stack into the web
    process on startup, which api/main.py deliberately avoids -- the read-only
    browsing endpoints have no business loading a vision framework. The import
    happens when a capture actually begins. tests/test_api.py enforces that
    `import api.main` stays clean.

TIMESTAMP CAVEAT
    Frames are timestamped on arrival using the server's monotonic clock, not by
    the browser. Over loopback the difference is sub-millisecond, and the metrics
    already tolerate variable frame intervals because they use real timestamps
    rather than assuming a fixed rate. It does mean a stalled browser tab shows up
    as slow head motion rather than as dropped frames.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .repository import DEFAULT_SESSIONS_DIR, REPO_ROOT

log = logging.getLogger("api.capture")

router = APIRouter()

MODEL_PATH = REPO_ROOT / "models" / "face_landmarker.task"

# Module-level so tests can redirect writes away from the real sessions/ directory.
sessions_dir: Path = DEFAULT_SESSIONS_DIR

# Guard rails on client-supplied values.
MIN_TARGET_REPS = 1
MAX_TARGET_REPS = 30
MAX_DURATION_S = 300.0
MAX_FRAME_BYTES = 4 * 1024 * 1024


class CaptureError(Exception):
    """Something the client should be told about in plain language."""


def _clamp_reps(value) -> int:
    try:
        reps = int(value)
    except (TypeError, ValueError):
        return 5
    return max(MIN_TARGET_REPS, min(MAX_TARGET_REPS, reps))


def _symptom_score(value):
    """Validate the 0-10 self-report, treating anything else as not provided."""
    if value is None:
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 10 else None


class CaptureRunner:
    """Owns one capture: a tracker, a session, and the thread they run on.

    MediaPipe's VIDEO running mode expects sequential calls with strictly
    increasing timestamps, so all inference for a given landmarker is pinned to a
    single worker thread rather than being spread across the default executor.
    Keeping it off the event loop stops a capture from blocking the read-only
    endpoints served by the same process.
    """

    def __init__(self, target_reps: int):
        if not MODEL_PATH.exists():
            raise CaptureError(
                f"Face landmark model not found at {MODEL_PATH}. Download it with "
                "the curl command in README.md before capturing."
            )

        # Lazy, per the module docstring.
        import cv2
        from session.voms_session import SessionConfig, VOMSSession
        from tracking.face_tracker import FaceTracker

        self._cv2 = cv2
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vms-capture")
        self._tracker = FaceTracker(str(MODEL_PATH))
        self._session = VOMSSession(
            config=SessionConfig(target_reps=target_reps, max_duration_s=MAX_DURATION_S)
        )
        self._session.start_session()

        self._started_monotonic = time.monotonic()
        self._last_ts_ms = -1
        self._frame_index = 0

    # ---- per-frame ------------------------------------------------------

    def _next_timestamp_ms(self) -> int:
        elapsed_ms = int((time.monotonic() - self._started_monotonic) * 1000)
        # MediaPipe rejects non-increasing timestamps, and two frames can easily
        # land in the same millisecond over loopback.
        if elapsed_ms <= self._last_ts_ms:
            elapsed_ms = self._last_ts_ms + 1
        self._last_ts_ms = elapsed_ms
        return elapsed_ms

    def _process_sync(self, payload: bytes):
        """Runs on the dedicated worker thread."""
        import numpy as np

        buffer = np.frombuffer(payload, dtype=np.uint8)
        image = self._cv2.imdecode(buffer, self._cv2.IMREAD_COLOR)
        if image is None:
            raise CaptureError("A frame could not be decoded as an image.")

        timestamp_ms = self._next_timestamp_ms()
        record = self._tracker.process(image, timestamp_ms, self._frame_index)
        self._frame_index += 1
        self._session.record_frame(record)

        return {
            "type": "progress",
            "frames": self._frame_index,
            "face": record.face_detected,
            "yaw": (
                round(record.head_yaw, 1) if record.head_yaw is not None else None
            ),
            "reps": self._session.completed_reps(),
            "elapsed_s": round(self._session.elapsed_s(), 2),
            "complete": self._session.is_complete(),
        }

    async def process(self, payload: bytes) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._process_sync, payload)

    # ---- finish ---------------------------------------------------------

    def _finish_sync(self, symptom_score, sessions_dir: Path) -> dict:
        from session_io import save_session

        result = self._session.end_session(symptom_score=symptom_score)
        saved = save_session(result, out_dir=sessions_dir, score=True)
        summary = saved.result.get("screening_summary") or {}
        return {
            "type": "saved",
            "id": saved.session_id,
            "severity_tier": summary.get("severity_tier"),
            "status": summary.get("status"),
            "composite_score": summary.get("composite_score"),
            "frames": self._frame_index,
        }

    async def finish(self, symptom_score, sessions_dir: Path) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._finish_sync, symptom_score, sessions_dir
        )

    def close(self):
        try:
            self._tracker.close()
        except Exception:  # noqa: BLE001 - never let cleanup mask the real error
            log.exception("failed to close face tracker")
        self._executor.shutdown(wait=False)


@router.websocket("/ws/capture")
async def capture(websocket: WebSocket):
    """Protocol:

        client -> {"type": "start", "target_reps": 5}
        server -> {"type": "ready"}
        client -> <binary JPEG frame>            (repeatedly)
        server -> {"type": "progress", ...}      (one per frame)
        client -> {"type": "finish", "symptom_score": 4 | null}
        server -> {"type": "saved", "id": "...", ...}

    Disconnecting before "finish" discards the capture. That is deliberate:
    writing a session the user walked away from would litter the dashboard with
    records nobody chose to keep.
    """
    await websocket.accept()
    runner: CaptureRunner | None = None

    try:
        opening = await websocket.receive_json()
        if not isinstance(opening, dict) or opening.get("type") != "start":
            await websocket.send_json(
                {"type": "error", "detail": "Expected a 'start' message first."}
            )
            return

        runner = CaptureRunner(_clamp_reps(opening.get("target_reps")))
        await websocket.send_json({"type": "ready", "target_reps": runner._session.config.target_reps})

        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            payload = message.get("bytes")
            if payload is not None:
                if len(payload) > MAX_FRAME_BYTES:
                    await websocket.send_json(
                        {"type": "error", "detail": "Frame too large."}
                    )
                    return
                await websocket.send_json(await runner.process(payload))
                continue

            text = message.get("text")
            if text is None:
                continue

            try:
                command = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "detail": "Expected JSON."}
                )
                continue

            kind = command.get("type") if isinstance(command, dict) else None
            if kind == "finish":
                saved = await runner.finish(
                    _symptom_score(command.get("symptom_score")),
                    sessions_dir,
                )
                await websocket.send_json(saved)
                return
            if kind == "abort":
                log.info("capture aborted by client; nothing written")
                return

    except WebSocketDisconnect:
        log.info("capture socket closed before finish; nothing written")
    except CaptureError as exc:
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except RuntimeError:
            pass
    except Exception as exc:  # noqa: BLE001 - surface the reason to the client
        log.exception("capture failed")
        try:
            await websocket.send_json(
                {"type": "error", "detail": f"Capture failed: {exc}"}
            )
        except RuntimeError:
            pass
    finally:
        if runner is not None:
            runner.close()


@router.get("/capture/status")
def capture_status():
    """Whether browser capture can work, so the UI can explain rather than fail."""
    return {
        "model_present": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH),
        "sessions_dir": str(sessions_dir),
    }
