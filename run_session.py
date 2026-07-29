"""CLI entrypoint: run one VOMS visual-motion subtest session and emit JSON.

Examples:
    python run_session.py
    python run_session.py --reps 5 --preview
    python run_session.py --source path/to/clip.mp4 --symptom-score 3
    python run_session.py --score          # also append screening + exercise blocks
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from camera.capture import FrameSource
from scoring.pipeline import describe, enrich_session
from session.voms_session import SessionConfig, VOMSSession
from tracking.face_tracker import DEFAULT_MODEL_PATH, FaceTracker

SESSIONS_DIR = Path("sessions")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Run one VOMS visual-motion subtest session.")
    p.add_argument("--source", default="0",
                   help="Webcam index (e.g. 0) or path to a video file. Default: 0")
    p.add_argument("--model", default=DEFAULT_MODEL_PATH,
                   help=f"Path to face_landmarker.task. Default: {DEFAULT_MODEL_PATH}")
    p.add_argument("--reps", type=int, default=5,
                   help="Target head-rotation reps (one rep = left-right-left). Default: 5")
    p.add_argument("--fps", type=float, default=30.0, help="Target capture FPS. Default: 30")
    p.add_argument("--max-duration", type=float, default=120.0,
                   help="Hard stop in seconds. Default: 120")
    p.add_argument("--preview", action="store_true",
                   help="Show a live preview window (press q to stop early).")
    p.add_argument("--symptom-score", type=int, default=None,
                   help="0-10 self-reported provocation. Skips the interactive prompt.")
    p.add_argument("--no-prompt", action="store_true",
                   help="Do not prompt for a symptom score; record it as null.")
    p.add_argument("--out-dir", default=str(SESSIONS_DIR),
                   help="Directory for saved session JSON. Default: sessions/")
    p.add_argument("--score", action="store_true",
                   help="Append screening_summary and recommended_exercises blocks "
                        "to the output (same logic as score_session.py).")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return p.parse_args(argv)


def resolve_source(raw: str):
    return int(raw) if raw.isdigit() else raw


def prompt_symptom_score() -> int | None:
    """Ask for the post-test 0-10 provocation rating (stubbed stand-in for a real UI)."""
    print("\n--- Post-test symptom report ---")
    print("How much did that provoke your symptoms (dizziness, nausea, headache, fogginess)?")
    for _ in range(3):
        try:
            raw = input("Enter a score 0-10 (or blank to skip): ").strip()
        except EOFError:
            return None
        if raw == "":
            return None
        try:
            score = int(raw)
        except ValueError:
            print("  Not a number. Try again.")
            continue
        if 0 <= score <= 10:
            return score
        print("  Out of range. Must be 0-10.")
    print("  Too many invalid attempts; recording no score.")
    return None


def validate_score(score: int | None) -> int | None:
    if score is None:
        return None
    if not 0 <= score <= 10:
        sys.exit(f"error: --symptom-score must be 0-10, got {score}")
    return score


def main(argv=None):
    args = parse_args(argv)
    source = resolve_source(args.source)

    if not Path(args.model).exists():
        sys.exit(
            f"error: model not found at {args.model}\n"
            "Download it with:\n  curl -L -o models/face_landmarker.task "
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/latest/face_landmarker.task"
        )

    config = SessionConfig(target_reps=args.reps, max_duration_s=args.max_duration)
    session = VOMSSession(config=config)

    if not args.quiet:
        print("VOMS visual-motion subtest")
        print("Hold your thumb at arm's length and keep your eyes locked on it.")
        print(f"Rotate head, eyes and trunk together, left and right, for {args.reps} reps.")
        print("Starting capture... (Ctrl+C to abort)\n")

    reps_shown = -1
    try:
        with FrameSource(source, target_fps=args.fps) as src, FaceTracker(args.model) as tracker:
            session.start_session()
            for frame in src.frames():
                record = tracker.process(frame.image_bgr, frame.timestamp_ms, frame.index)
                session.record_frame(record)

                reps = session.completed_reps()
                if not args.quiet and reps != reps_shown:
                    reps_shown = reps
                    print(f"  reps: {reps}/{args.reps}")

                if args.preview:
                    img = frame.image_bgr.copy()
                    label = f"reps {reps}/{args.reps}"
                    if record.head_yaw is not None:
                        label += f"  yaw {record.head_yaw:+.1f}"
                    if not record.face_detected:
                        label = "NO FACE DETECTED"
                    cv2.putText(img, label, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                                (0, 255, 0) if record.face_detected else (0, 0, 255), 2)
                    cv2.imshow("VOMS session (press q to stop)", img)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if session.is_complete():
                    break
    except KeyboardInterrupt:
        if not args.quiet:
            print("\nCapture interrupted by user; finalizing what was recorded.")
    finally:
        if args.preview:
            cv2.destroyAllWindows()

    if args.symptom_score is not None:
        score = validate_score(args.symptom_score)
    elif args.no_prompt or not sys.stdin.isatty():
        score = None
    else:
        score = prompt_symptom_score()

    result = session.end_session(symptom_score=score)

    # Optional scoring step. Uses the same enrich_session() as score_session.py so
    # a live run and a later re-score of the saved file cannot disagree.
    if args.score:
        result = enrich_session(result)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = ".scored.json" if args.score else ".json"
    out_path = out_dir / f"session_{stamp}{suffix}"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    if not args.quiet:
        if args.score:
            print(f"\n{describe(result)}", file=sys.stderr)
        print(f"Saved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
