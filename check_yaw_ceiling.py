"""Measure how far the head can rotate before face tracking degrades.

WHY THIS EXISTS
    The standardized VOMS visual-motion protocol calls for 80 degrees of rotation
    to each side. At that angle the face is close to profile, and MediaPipe's
    landmarker is expected to degrade. If +/-80 degrees is not trackable with a
    single front-facing webcam, then protocol-faithful capture is impossible with
    this hardware and the tool's numbers can never be compared to published norms
    -- which is a limitation to state, not to discover later.

    This script measures where that ceiling actually is, by binning tracking
    quality against absolute yaw.

HOW TO RUN IT
    python check_yaw_ceiling.py --preview

    Rotate your head slowly and progressively further -- small turns first, then
    wider, until you are turning as far as you comfortably can. Hold briefly at
    each extreme so the wider bins collect samples. Roughly 60 seconds is plenty.

READING THE OUTPUT
    The table reports, per 10-degree yaw bin: how many frames landed there, the
    share with a face detected, and mean landmark confidence. The ceiling is the
    bin where detection rate starts falling away from ~1.0.

    A caveat that matters: yaw is only reported when a face IS detected, so
    detection failures cannot be attributed to a bin directly. The frame count per
    bin is therefore the honest signal -- if bins beyond some angle are empty or
    sparse while you know you rotated further, tracking was failing there. That is
    why total dropped frames are reported separately.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import cv2
import numpy as np

from camera.capture import FrameSource
from tracking.face_tracker import DEFAULT_MODEL_PATH, FaceTracker

BIN_WIDTH_DEG = 10.0


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Measure the yaw angle at which face tracking degrades."
    )
    p.add_argument("--source", default="0", help="Webcam index or video path. Default: 0")
    p.add_argument("--model", default=DEFAULT_MODEL_PATH)
    p.add_argument("--duration", type=float, default=60.0,
                   help="Capture length in seconds. Default: 60")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--preview", action="store_true",
                   help="Show a live window with the current yaw (press q to stop).")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    source = int(args.source) if args.source.isdigit() else args.source

    print("Yaw ceiling check")
    print("Rotate your head slowly and progressively wider, holding briefly at each")
    print("extreme. Keep your eyes on your thumb as in the real test.")
    print(f"Capturing for up to {args.duration:.0f}s (Ctrl+C to stop early)\n")

    bins = defaultdict(lambda: {"frames": 0, "detected": 0, "confidence": []})
    total = dropped = 0
    max_abs_yaw = 0.0
    last_yaw = None

    try:
        with FrameSource(source, target_fps=args.fps) as src, \
                FaceTracker(args.model) as tracker:
            for frame in src.frames():
                if frame.timestamp_ms / 1000.0 > args.duration:
                    break
                record = tracker.process(frame.image_bgr, frame.timestamp_ms, frame.index)
                total += 1

                if not record.face_detected or record.head_yaw is None:
                    dropped += 1
                    # Attribute the miss to the last known bin: the head was near
                    # there when tracking gave out.
                    if last_yaw is not None:
                        key = int(abs(last_yaw) // BIN_WIDTH_DEG)
                        bins[key]["frames"] += 1
                else:
                    last_yaw = record.head_yaw
                    max_abs_yaw = max(max_abs_yaw, abs(record.head_yaw))
                    key = int(abs(record.head_yaw) // BIN_WIDTH_DEG)
                    bins[key]["frames"] += 1
                    bins[key]["detected"] += 1
                    if record.landmark_confidence is not None:
                        bins[key]["confidence"].append(record.landmark_confidence)

                if args.preview:
                    img = frame.image_bgr.copy()
                    if record.face_detected and record.head_yaw is not None:
                        label = f"yaw {record.head_yaw:+.1f}  max |yaw| {max_abs_yaw:.1f}"
                        colour = (0, 255, 0)
                    else:
                        label = "NO FACE DETECTED"
                        colour = (0, 0, 255)
                    cv2.putText(img, label, (12, 32), cv2.FONT_HERSHEY_SIMPLEX,
                                0.8, colour, 2)
                    cv2.imshow("yaw ceiling check (press q to stop)", img)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    except KeyboardInterrupt:
        print("\nInterrupted; reporting what was collected.")
    finally:
        if args.preview:
            cv2.destroyAllWindows()

    if not total:
        print("No frames captured.")
        return 1

    print(f"\n{'|yaw| bin':>14}  {'frames':>7}  {'detect rate':>11}  {'mean conf':>9}")
    print("-" * 48)
    for key in sorted(bins):
        low, high = key * BIN_WIDTH_DEG, (key + 1) * BIN_WIDTH_DEG
        data = bins[key]
        rate = data["detected"] / data["frames"] if data["frames"] else 0.0
        conf = np.mean(data["confidence"]) if data["confidence"] else float("nan")
        print(f"{low:5.0f}-{high:<5.0f}deg  {data['frames']:>7}  {rate:>11.3f}  {conf:>9.3f}")

    print(f"\ntotal frames: {total}   frames with no face: {dropped} "
          f"({dropped / total:.1%})")
    print(f"widest tracked |yaw|: {max_abs_yaw:.1f} deg")
    print("\nThe protocol asks for 80 deg each side. Compare that against the widest")
    print("tracked angle above, and against the bin where detect rate leaves ~1.0.")
    print("If tracking dies well short of 80 deg, protocol-faithful capture is not")
    print("possible with this camera setup -- record that as a stated limitation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
