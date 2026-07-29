"""Tests for browser-driven capture (api/capture.py).

Run directly (no pytest needed):

    .venv\\Scripts\\activate
    python tests/test_capture.py

The end-to-end tests push real JPEG bytes through the real MediaPipe pipeline, so
they are slower than the other suites. They use synthetic images rather than a
webcam: no face is detected in them, which is itself the interesting case --
capture must still finish, still save, and honestly report that nothing was
tracked rather than inventing a result.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2                                                        # noqa: E402
from fastapi.testclient import TestClient                         # noqa: E402

from api import capture as capture_module                         # noqa: E402
from api import main as api_main                                  # noqa: E402
from api.repository import SessionRepository                      # noqa: E402


def jpeg_frame(width=320, height=240, shade=90) -> bytes:
    """A plain JPEG frame. No face in it, deliberately."""
    image = np.full((height, width, 3), shade, dtype=np.uint8)
    # A little structure so the encoder does not produce a degenerate image.
    cv2.rectangle(image, (40, 40), (width - 40, height - 40), (150, 150, 150), 3)
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    assert ok, "failed to encode test frame"
    return buffer.tobytes()


class CaptureHarness:
    """Points capture writes at a temp directory and yields a TestClient."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="vms_capture_"))
        self._original_dir = capture_module.sessions_dir
        self._original_repo = api_main.repository
        capture_module.sessions_dir = self.dir
        api_main.repository = SessionRepository(self.dir)
        self.client = TestClient(api_main.app)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        capture_module.sessions_dir = self._original_dir
        api_main.repository = self._original_repo
        shutil.rmtree(self.dir, ignore_errors=True)

    def files(self):
        return sorted(p.name for p in self.dir.iterdir())


# ---- input validation ----------------------------------------------------

def test_clamp_reps_bounds_and_fallback():
    clamp = capture_module._clamp_reps
    assert clamp(5) == 5
    assert clamp(0) == capture_module.MIN_TARGET_REPS
    assert clamp(9999) == capture_module.MAX_TARGET_REPS
    # Junk falls back to the protocol default rather than raising at the socket.
    assert clamp(None) == 5
    assert clamp("abc") == 5
    assert clamp(3.7) == 3


def test_symptom_score_validation():
    score = capture_module._symptom_score
    assert score(0) == 0, "0 is a real score (no symptoms), not a missing value"
    assert score(10) == 10
    assert score(None) is None
    assert score(11) is None
    assert score(-1) is None
    assert score("nonsense") is None
    assert score("7") == 7


# ---- status endpoint -----------------------------------------------------

def test_capture_status_reports_model_presence():
    with CaptureHarness() as harness:
        body = harness.client.get("/capture/status").json()
        assert "model_present" in body
        assert body["sessions_dir"] == str(harness.dir)


# ---- protocol handling ---------------------------------------------------

def test_first_message_must_be_start():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "finish"})
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "start" in reply["detail"].lower()


def test_start_acknowledges_with_clamped_target():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 500})
            reply = ws.receive_json()
            assert reply["type"] == "ready"
            assert reply["target_reps"] == capture_module.MAX_TARGET_REPS


def test_oversized_frame_is_rejected():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(b"\x00" * (capture_module.MAX_FRAME_BYTES + 1))
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "too large" in reply["detail"].lower()


def test_undecodable_frame_reports_an_error():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(b"this is not a jpeg")
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "decode" in reply["detail"].lower()


def test_malformed_json_does_not_kill_the_socket():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            assert ws.receive_json()["type"] == "ready"
            ws.send_text("{not json")
            assert ws.receive_json()["type"] == "error"
            # Still alive: a frame is still accepted afterwards.
            ws.send_bytes(jpeg_frame())
            assert ws.receive_json()["type"] == "progress"


# ---- end to end ----------------------------------------------------------

def test_frames_produce_progress_updates():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            assert ws.receive_json()["type"] == "ready"

            for expected in range(1, 4):
                ws.send_bytes(jpeg_frame())
                progress = ws.receive_json()
                assert progress["type"] == "progress"
                assert progress["frames"] == expected
                # No face in a synthetic frame, and that must be reported.
                assert progress["face"] is False
                assert progress["yaw"] is None
                assert progress["reps"] == 0


def test_finish_writes_raw_and_scored_files():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            assert ws.receive_json()["type"] == "ready"
            for _ in range(4):
                ws.send_bytes(jpeg_frame())
                ws.receive_json()
            ws.send_json({"type": "finish", "symptom_score": 4})
            saved = ws.receive_json()

        assert saved["type"] == "saved", saved
        session_id = saved["id"]
        # Both files, matching what run_session.py writes via the same helper.
        assert harness.files() == [
            f"session_{session_id}.json",
            f"session_{session_id}.scored.json",
        ], harness.files()


def test_saved_session_records_the_symptom_score_and_no_tracking():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            ws.receive_json()
            for _ in range(4):
                ws.send_bytes(jpeg_frame())
                ws.receive_json()
            ws.send_json({"type": "finish", "symptom_score": 7})
            saved = ws.receive_json()

        path = harness.dir / f"session_{saved['id']}.scored.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["self_reported_symptoms"]["score"] == 7
        assert data["self_reported_symptoms"]["provided"] is True
        assert data["tracking_quality"]["face_detection_rate"] == 0.0
        # No face anywhere, so the objective signal must be reported unusable
        # rather than scored -- the tier rests on the symptom report alone.
        summary = data["screening_summary"]
        assert summary["status"] == "symptom_only", summary["status"]
        assert summary["data_quality"]["objective_signal_usable"] is False
        assert summary["severity_tier"] == "pronounced"  # 7 * 10 = 70 composite


def test_zero_symptom_score_is_preserved_through_capture():
    """0 must survive as a real score, not collapse to 'not provided'."""
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            ws.receive_json()
            ws.send_bytes(jpeg_frame())
            ws.receive_json()
            ws.send_json({"type": "finish", "symptom_score": 0})
            saved = ws.receive_json()

        data = json.loads(
            (harness.dir / f"session_{saved['id']}.scored.json").read_text(encoding="utf-8")
        )
        assert data["self_reported_symptoms"]["score"] == 0
        assert data["self_reported_symptoms"]["provided"] is True


def test_finish_without_a_score_is_allowed():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            ws.receive_json()
            ws.send_bytes(jpeg_frame())
            ws.receive_json()
            ws.send_json({"type": "finish", "symptom_score": None})
            saved = ws.receive_json()

        data = json.loads(
            (harness.dir / f"session_{saved['id']}.scored.json").read_text(encoding="utf-8")
        )
        assert data["self_reported_symptoms"]["score"] is None
        assert data["self_reported_symptoms"]["provided"] is False


def test_abort_writes_nothing():
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            ws.receive_json()
            for _ in range(3):
                ws.send_bytes(jpeg_frame())
                ws.receive_json()
            ws.send_json({"type": "abort"})
        assert harness.files() == [], harness.files()


def test_disconnect_before_finish_writes_nothing():
    """A closed tab must not litter the dashboard with unwanted sessions."""
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            ws.receive_json()
            ws.send_bytes(jpeg_frame())
            ws.receive_json()
            # Leaving the context manager closes the socket without "finish".
        assert harness.files() == [], harness.files()


def test_captured_session_appears_in_the_listing():
    """The whole point: a browser capture must show up in the dashboard."""
    with CaptureHarness() as harness:
        with harness.client.websocket_connect("/ws/capture") as ws:
            ws.send_json({"type": "start", "target_reps": 5})
            ws.receive_json()
            for _ in range(3):
                ws.send_bytes(jpeg_frame())
                ws.receive_json()
            ws.send_json({"type": "finish", "symptom_score": 5})
            saved = ws.receive_json()

        listing = harness.client.get("/sessions").json()
        ids = [s["id"] for s in listing["sessions"]]
        assert saved["id"] in ids, ids

        detail = harness.client.get(f"/sessions/{saved['id']}")
        assert detail.status_code == 200
        assert detail.json()["summary"]["symptom_score"] == 5


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
