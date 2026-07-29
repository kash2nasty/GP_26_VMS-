"""Tests for the read-only session API.

Run directly (no pytest needed):

    .venv\\Scripts\\activate
    python tests/test_api.py

Fixtures write real files to a temp directory, because the thing most likely to
break here is filename handling -- ".scored.json" also ends with ".json", and the
three on-disk shapes (raw+scored, scored-only, raw-only) each take a different
path through the loader.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient                          # noqa: E402

from api import main as api_main                                   # noqa: E402
from api.repository import (                                       # noqa: E402
    TRASH_DIRNAME,
    SessionNotFound,
    SessionRepository,
    split_filename,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# 2026-07-29T02:48:16Z
STARTED_AT = 1785293296.0


def make_session(symptom_score=6, tier="moderate", scored=True, fidelity=True,
                 scoring_version="0.2.0", started_at=STARTED_AT):
    """Minimal session dict shaped like the real files."""
    data = {
        "schema_version": "0.1.0",
        "test_type": "VOMS_visual_motion_subtest",
        "disclaimer": "This output is a screening data point only...",
        "session": {
            "started_at_unix": started_at,
            "ended_at_unix": started_at + 20.0,
            "duration_s": 20.0,
            "target_reps": 5,
        },
        "tracking_quality": {"face_detection_rate": 1.0, "total_frames": 352},
        "self_reported_symptoms": {
            "scale": "0-10", "score": symptom_score,
            "provided": symptom_score is not None,
        },
        "head_motion": {
            "insufficient_data": False, "completed_reps": 5,
            "mean_sweep_amplitude_deg": 75.8, "mean_sweep_duration_s": 1.65,
            "sweep_duration_cv": 0.16, "roll_range_deg": 58.6,
            "pitch_range_deg": 30.1,
        },
        "gaze_stability": {
            "insufficient_data": False, "compensation_r2": 0.73,
            "fixation_stability_score": 31.6, "frames_excluded_blink": 5,
        },
    }
    if scored:
        screening = {
            "scoring_schema_version": scoring_version,
            "status": "scored",
            "severity_tier": tier,
            "composite_score": 75.36,
            "data_quality": {"objective_signal_usable": True, "gates_failed": []},
            "notes": [],
            "disclaimer": "screening disclaimer",
        }
        if fidelity:
            screening["protocol_fidelity"] = {
                "comparable_to_clinical_protocol": False,
                "advisory_flags": ["amplitude_below_protocol"],
            }
        data["screening_summary"] = screening
        data["recommended_exercises"] = {
            "severity_tier": tier,
            "exercises": [{"id": "eye_movements_slow_then_fast", "name": "Eye movements"}],
            "disclaimer": "exercise disclaimer",
            "safety_note": "safety note",
        }
    return data


class TempSessions:
    """Temp directory holding session files, with the repo pointed at it."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="vms_sessions_"))

    def write(self, session_id, data, scored):
        suffix = ".scored.json" if scored else ".json"
        path = self.dir / f"session_{session_id}{suffix}"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def write_raw_text(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def repo(self):
        return SessionRepository(self.dir)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


# ---- filename parsing ----------------------------------------------------

def test_scored_suffix_is_matched_before_json():
    """'.scored.json' also ends with '.json'; order of checks matters."""
    assert split_filename("session_20260729T024816Z.scored.json") == (
        "20260729T024816Z", True
    )
    assert split_filename("session_20260729T024816Z.json") == (
        "20260729T024816Z", False
    )


def test_prefix_is_optional():
    assert split_filename("20260729T024816Z.json") == ("20260729T024816Z", False)


def test_non_json_files_are_ignored():
    for name in ("notes.txt", "session_x.csv", "README.md", ".gitkeep"):
        assert split_filename(name) == (None, False), name


def test_bare_suffix_yields_no_id():
    assert split_filename(".json") == (None, False)
    assert split_filename("session_.json") == (None, False)


# ---- discovery -----------------------------------------------------------

def test_raw_and_scored_pair_is_one_session():
    tmp = TempSessions()
    try:
        tmp.write("20260729T024816Z", make_session(scored=False), scored=False)
        tmp.write("20260729T024816Z", make_session(), scored=True)
        found = tmp.repo().discover()
        assert list(found) == ["20260729T024816Z"], list(found)
        entry = found["20260729T024816Z"]
        assert entry.raw_path is not None and entry.scored_path is not None
    finally:
        tmp.cleanup()


def test_scored_file_is_preferred_over_raw():
    """The stored score must win, not a recomputed one."""
    tmp = TempSessions()
    try:
        tmp.write("s1", make_session(scored=False), scored=False)
        tmp.write("s1", make_session(tier="pronounced"), scored=True)
        result = tmp.repo().load("s1")
        assert result.scoring_source == "file"
        assert result.session["screening_summary"]["severity_tier"] == "pronounced"
    finally:
        tmp.cleanup()


def test_scored_only_session_loads():
    """The real 031327Z case: an older --score run wrote no raw file."""
    tmp = TempSessions()
    try:
        tmp.write("s2", make_session(tier="pronounced"), scored=True)
        result = tmp.repo().load("s2")
        assert result.scoring_source == "file"
        assert result.session["screening_summary"]["severity_tier"] == "pronounced"
    finally:
        tmp.cleanup()


def test_raw_only_session_is_scored_in_memory():
    """A capture saved without --score still gets a tier, flagged as computed."""
    tmp = TempSessions()
    try:
        tmp.write("s3", make_session(scored=False), scored=False)
        result = tmp.repo().load("s3")
        assert result.scoring_source == "computed"
        assert result.session["screening_summary"]["severity_tier"] is not None
        assert result.session["recommended_exercises"]["exercises"]
    finally:
        tmp.cleanup()


def test_in_memory_scoring_does_not_write_files():
    """This phase is read-only; loading must not create a .scored.json."""
    tmp = TempSessions()
    try:
        tmp.write("s4", make_session(scored=False), scored=False)
        before = sorted(p.name for p in tmp.dir.iterdir())
        tmp.repo().load("s4")
        assert sorted(p.name for p in tmp.dir.iterdir()) == before
    finally:
        tmp.cleanup()


def test_missing_session_raises():
    tmp = TempSessions()
    try:
        try:
            tmp.repo().load("nope")
        except SessionNotFound:
            pass
        else:
            raise AssertionError("expected SessionNotFound")
    finally:
        tmp.cleanup()


def test_missing_directory_is_empty_not_an_error():
    repo = SessionRepository(Path(tempfile.gettempdir()) / "vms_definitely_absent_dir")
    assert repo.discover() == {}
    assert repo.list_summaries() == ([], [])


# ---- summaries -----------------------------------------------------------

def test_summary_fields():
    tmp = TempSessions()
    try:
        tmp.write("s5", make_session(symptom_score=8, tier="pronounced"), scored=True)
        summary = tmp.repo().summarize(tmp.repo().load("s5"))
        assert summary["id"] == "s5"
        assert summary["symptom_score"] == 8
        assert summary["severity_tier"] == "pronounced"
        assert summary["completed_reps"] == 5
        assert summary["face_detection_rate"] == 1.0
        assert summary["comparable_to_clinical_protocol"] is False
        assert summary["scoring_schema_version"] == "0.2.0"
    finally:
        tmp.cleanup()


def test_absent_fidelity_is_none_not_false():
    """A v0.1.0 score was never assessed for fidelity -- that is not 'not comparable'.

    The real 031327Z file has this shape. Collapsing it to False would tell the
    viewer the session failed a check that never ran.
    """
    tmp = TempSessions()
    try:
        tmp.write("s6", make_session(fidelity=False, scoring_version="0.1.0"), scored=True)
        summary = tmp.repo().summarize(tmp.repo().load("s6"))
        assert summary["comparable_to_clinical_protocol"] is None
        assert summary["scoring_schema_version"] == "0.1.0"
    finally:
        tmp.cleanup()


def test_captured_at_prefers_recorded_start_over_filename():
    """started_at_unix is when capture began; the filename stamp is when it ended."""
    tmp = TempSessions()
    try:
        # Filename says 03:00:00, recorded start says 02:48:16.
        tmp.write("20260729T030000Z", make_session(started_at=STARTED_AT), scored=True)
        result = tmp.repo().load("20260729T030000Z")
        assert result.captured_at == "2026-07-29T02:48:16Z", result.captured_at
    finally:
        tmp.cleanup()


def test_captured_at_falls_back_to_filename_stamp():
    tmp = TempSessions()
    try:
        data = make_session()
        del data["session"]["started_at_unix"]
        tmp.write("20260729T030000Z", data, scored=True)
        result = tmp.repo().load("20260729T030000Z")
        assert result.captured_at == "2026-07-29T03:00:00Z", result.captured_at
    finally:
        tmp.cleanup()


def test_unparseable_timestamp_is_none_not_a_crash():
    tmp = TempSessions()
    try:
        data = make_session()
        del data["session"]["started_at_unix"]
        tmp.write("not-a-timestamp", data, scored=True)
        assert tmp.repo().load("not-a-timestamp").captured_at is None
    finally:
        tmp.cleanup()


def test_list_is_sorted_newest_first():
    tmp = TempSessions()
    try:
        for stamp, started in [
            ("20260729T010000Z", 1785290000.0),
            ("20260729T030000Z", 1785300000.0),
            ("20260729T020000Z", 1785295000.0),
        ]:
            tmp.write(stamp, make_session(started_at=started), scored=True)
        summaries, broken = tmp.repo().list_summaries()
        assert broken == []
        assert [s["id"] for s in summaries] == [
            "20260729T030000Z", "20260729T020000Z", "20260729T010000Z"
        ], [s["id"] for s in summaries]
    finally:
        tmp.cleanup()


def test_undated_sessions_sort_last_without_crashing():
    """A None timestamp must not break the sort comparison."""
    tmp = TempSessions()
    try:
        data = make_session()
        del data["session"]["started_at_unix"]
        tmp.write("zzz-undated", data, scored=True)
        tmp.write("20260729T030000Z", make_session(), scored=True)
        summaries, _ = tmp.repo().list_summaries()
        assert summaries[-1]["id"] == "zzz-undated", [s["id"] for s in summaries]
    finally:
        tmp.cleanup()


def test_malformed_file_is_reported_not_fatal():
    """One bad file must not take down the whole list, nor vanish silently."""
    tmp = TempSessions()
    try:
        tmp.write("good", make_session(), scored=True)
        tmp.write_raw_text("session_bad.scored.json", '{"truncated')
        summaries, broken = tmp.repo().list_summaries()
        assert [s["id"] for s in summaries] == ["good"]
        assert [b["id"] for b in broken] == ["bad"], broken
    finally:
        tmp.cleanup()


def test_non_object_json_is_reported_as_broken():
    tmp = TempSessions()
    try:
        tmp.write_raw_text("session_list.json", "[1, 2, 3]")
        summaries, broken = tmp.repo().list_summaries()
        assert summaries == []
        assert [b["id"] for b in broken] == ["list"]
    finally:
        tmp.cleanup()


# ---- HTTP layer ----------------------------------------------------------

class ApiClient:
    """TestClient with the app's repository pointed at a temp directory."""

    def __init__(self, tmp: TempSessions):
        self.tmp = tmp
        self.original = api_main.repository
        api_main.repository = tmp.repo()
        self.client = TestClient(api_main.app)

    def __enter__(self):
        return self.client

    def __exit__(self, *exc):
        api_main.repository = self.original


def test_health_endpoint():
    tmp = TempSessions()
    try:
        with ApiClient(tmp) as client:
            body = client.get("/health").json()
            assert body["status"] == "ok"
    finally:
        tmp.cleanup()


def test_list_endpoint_shape():
    tmp = TempSessions()
    try:
        tmp.write("s7", make_session(symptom_score=8, tier="pronounced"), scored=True)
        with ApiClient(tmp) as client:
            response = client.get("/sessions")
            assert response.status_code == 200
            body = response.json()
            assert len(body["sessions"]) == 1
            assert body["sessions"][0]["severity_tier"] == "pronounced"
            assert body["unreadable"] == []
    finally:
        tmp.cleanup()


def test_detail_endpoint_shape():
    tmp = TempSessions()
    try:
        tmp.write("s8", make_session(), scored=True)
        with ApiClient(tmp) as client:
            body = client.get("/sessions/s8").json()
            assert body["id"] == "s8"
            assert body["summary"]["severity_tier"] == "moderate"
            assert body["session"]["gaze_stability"]["compensation_r2"] == 0.73
            assert body["session"]["recommended_exercises"]["exercises"]
    finally:
        tmp.cleanup()


def test_detail_404_for_unknown_id():
    tmp = TempSessions()
    try:
        with ApiClient(tmp) as client:
            assert client.get("/sessions/missing").status_code == 404
    finally:
        tmp.cleanup()


def test_every_results_response_carries_disclaimers():
    """The frontend must never have to supply this text itself."""
    tmp = TempSessions()
    try:
        tmp.write("s9", make_session(), scored=True)
        with ApiClient(tmp) as client:
            for path in ("/sessions", "/sessions/s9"):
                disclaimers = client.get(path).json()["disclaimers"]
                assert disclaimers["screening"], path
                assert disclaimers["exercises"], path
                assert disclaimers["safety_note"], path
    finally:
        tmp.cleanup()


def test_cors_allows_the_next_dev_server():
    tmp = TempSessions()
    try:
        with ApiClient(tmp) as client:
            response = client.get(
                "/sessions", headers={"Origin": "http://localhost:3000"}
            )
            assert response.headers.get("access-control-allow-origin") == (
                "http://localhost:3000"
            )
    finally:
        tmp.cleanup()


# ---- deletion ------------------------------------------------------------

def test_delete_moves_both_files_to_trash():
    """Files are moved, not unlinked, so a misclick stays recoverable."""
    tmp = TempSessions()
    try:
        tmp.write("d1", make_session(scored=False), scored=False)
        tmp.write("d1", make_session(), scored=True)
        repo = tmp.repo()

        moved = repo.delete("d1")
        assert sorted(moved) == ["session_d1.json", "session_d1.scored.json"], moved
        # Gone from the listing...
        assert repo.discover() == {}
        # ...but still on disk in the trash directory.
        trashed = sorted(p.name for p in (tmp.dir / TRASH_DIRNAME).iterdir())
        assert trashed == ["session_d1.json", "session_d1.scored.json"], trashed
    finally:
        tmp.cleanup()


def test_delete_of_scored_only_session():
    tmp = TempSessions()
    try:
        tmp.write("d2", make_session(), scored=True)
        repo = tmp.repo()
        assert repo.delete("d2") == ["session_d2.scored.json"]
        assert repo.discover() == {}
    finally:
        tmp.cleanup()


def test_trash_directory_is_not_listed_as_a_session():
    """The trash lives inside sessions/, so discovery must skip the directory."""
    tmp = TempSessions()
    try:
        tmp.write("d3", make_session(), scored=True)
        tmp.write("keep", make_session(), scored=True)
        repo = tmp.repo()
        repo.delete("d3")
        summaries, broken = repo.list_summaries()
        assert [s["id"] for s in summaries] == ["keep"], [s["id"] for s in summaries]
        assert broken == []
    finally:
        tmp.cleanup()


def test_delete_twice_does_not_clobber_the_first_copy():
    """Two sessions with the same filename must both survive in the trash."""
    tmp = TempSessions()
    try:
        tmp.write("d4", make_session(symptom_score=3), scored=True)
        repo = tmp.repo()
        repo.delete("d4")
        # Recreate the same id, then delete again.
        tmp.write("d4", make_session(symptom_score=9), scored=True)
        repo.delete("d4")
        trashed = sorted(p.name for p in (tmp.dir / TRASH_DIRNAME).iterdir())
        assert len(trashed) == 2, trashed
    finally:
        tmp.cleanup()


def test_delete_unknown_session_raises():
    tmp = TempSessions()
    try:
        try:
            tmp.repo().delete("nope")
        except SessionNotFound:
            pass
        else:
            raise AssertionError("expected SessionNotFound")
    finally:
        tmp.cleanup()


def test_delete_endpoint_returns_what_moved():
    tmp = TempSessions()
    try:
        tmp.write("d5", make_session(scored=False), scored=False)
        tmp.write("d5", make_session(), scored=True)
        with ApiClient(tmp) as client:
            response = client.delete("/sessions/d5")
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["id"] == "d5"
            assert sorted(body["deleted"]) == [
                "session_d5.json",
                "session_d5.scored.json",
            ]
            assert body["recoverable"] is True
            # And it is gone from the listing.
            assert client.get("/sessions").json()["sessions"] == []
            assert client.get("/sessions/d5").status_code == 404
    finally:
        tmp.cleanup()


def test_delete_endpoint_404_for_unknown_id():
    tmp = TempSessions()
    try:
        with ApiClient(tmp) as client:
            assert client.delete("/sessions/missing").status_code == 404
    finally:
        tmp.cleanup()


def test_delete_cannot_escape_the_sessions_directory():
    """`session_id` arrives from a URL, so traversal must be impossible.

    Paths come from discover(), which only ever yields names found on disk, so a
    traversal attempt simply matches nothing.
    """
    tmp = TempSessions()
    outside = tmp.dir.parent / "vms_outside_target.json"
    outside.write_text("{}", encoding="utf-8")
    try:
        for attempt in ("../vms_outside_target", "..%2Fvms_outside_target", "../.."):
            try:
                tmp.repo().delete(attempt)
            except SessionNotFound:
                pass
            else:
                raise AssertionError(f"traversal was not rejected: {attempt}")
        assert outside.exists(), "a file outside sessions/ was touched"
    finally:
        outside.unlink(missing_ok=True)
        tmp.cleanup()


# ---- architectural constraint -------------------------------------------

def test_api_does_not_import_mediapipe():
    """The API must not drag the camera stack into the web process.

    session.voms_session looks like the obvious source for the canonical
    disclaimer, but it imports tracking.face_tracker -> mediapipe. Checked in a
    subprocess because this test process has already imported mediapipe via the
    other suites.
    """
    code = (
        "import sys; import api.main; "
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('mediapipe', 'cv2', 'jax', 'jaxlib')]; "
        "print(','.join(sorted(bad)))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    leaked = proc.stdout.strip()
    assert leaked == "", f"api.main pulled in camera-stack modules: {leaked}"


def test_real_sessions_directory_loads():
    """Smoke test against whatever is actually in sessions/ right now."""
    repo = SessionRepository()
    if not repo.sessions_dir.is_dir():
        return
    summaries, broken = repo.list_summaries()
    assert broken == [], broken
    for summary in summaries:
        assert summary["id"]
        assert summary["scoring_source"] in ("file", "computed")


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
