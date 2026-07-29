# VMS Screening Tool — Camera + Backend Prototype

Digitizes the **visual-motion subtest of VOMS** (Vestibular/Ocular Motor Screening).

In the clinical version of this test, the patient holds a thumb at arm's length, keeps their
gaze locked on it, and rotates head + eyes + trunk together as one unit, left and right, for a
fixed number of reps. Afterward they rate symptom provocation 0-10. Poor gaze fixation *during*
head motion is the signal the test is looking for.

This phase captures and structures that data. **There is no UI, no diagnosis logic, and no
scoring interpretation** — just clean motion + symptom data for a later layer to consume.

> This tool produces a screening data point, not a medical diagnosis. Output must be reviewed
> by a qualified clinician. The `disclaimer` field is baked into the output schema so it can't
> be dropped later.

---

## Setup

Already done in this folder, but to reproduce from scratch:

```powershell
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

Then download the model bundle:

```powershell
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
```

### Why Python 3.12 and mediapipe 0.10.21 specifically

**Do not upgrade mediapipe past 0.10.21 without re-verifying.** Starting at 0.10.30, MediaPipe's
Windows wheels changed from properly-tagged per-Python builds (~50 MB) to generic
`py3-none-win_amd64` wheels of only ~10-16 MB. A 10 MB wheel cannot contain the compiled native
framework — this is the cause of the missing `mediapipe.framework` submodule on Windows. It
affects 0.10.30, 0.10.31, 0.10.32, 0.10.33, 0.10.35, and 1.0.0.

`0.10.21` (Feb 2025) is the last release with complete Windows builds. It ships wheels for
cp39-cp312 only, which is why the venv uses **Python 3.12** rather than the 3.13/3.14 installed
system-wide.

Verified working: 478 landmarks detected, facial transformation matrix present.

---

## Running a session

```powershell
.venv\Scripts\activate

python run_session.py                        # webcam, 5 reps, prompts for symptom score
python run_session.py --preview              # with a live preview window
python run_session.py --reps 10              # different rep count
python run_session.py --source clip.mp4      # replay a video file instead of a camera
python run_session.py --symptom-score 3      # skip the interactive prompt
```

The session ends when the target reps are detected, at `--max-duration`, on `q` in the preview
window, or on Ctrl+C (partial data is still written).

JSON goes to stdout **and** to `sessions/session_<UTC timestamp>.json`.

| Flag | Default | Meaning |
|---|---|---|
| `--source` | `0` | Webcam index, or a video file path |
| `--reps` | `5` | Target reps (1 rep = left-right-left) |
| `--fps` | `30` | Target capture FPS |
| `--max-duration` | `120` | Hard stop, seconds |
| `--preview` | off | Live window with yaw + rep counter |
| `--symptom-score` | — | Supply 0-10 non-interactively |
| `--no-prompt` | off | Record score as `null` |
| `--model` | `models/face_landmarker.task` | Model bundle path |

---

## Project structure

```
camera/capture.py          FrameSource — webcam or video file, same interface
tracking/face_tracker.py   MediaPipe Face Landmarker -> per-frame FrameRecord
tracking/landmarks.py      Landmark index constants (iris, eye corners)
session/voms_session.py    Session API + result assembly
session/metrics.py         Peak detection, angular velocity, gaze stability math
run_session.py             CLI entrypoint
tests/test_gaze_sign.py    Regression tests for the iris sign convention
models/                    face_landmarker.task
sessions/                  Saved session JSON
```

### Tests

Plain asserts, no pytest required:

```powershell
python tests/test_gaze_sign.py
```

### Programmatic API

```python
from camera.capture import FrameSource
from tracking.face_tracker import FaceTracker
from session.voms_session import VOMSSession, SessionConfig

session = VOMSSession(config=SessionConfig(target_reps=5))
with FrameSource(0) as src, FaceTracker() as tracker:
    session.start_session()
    for frame in src.frames():
        record = tracker.process(frame.image_bgr, frame.timestamp_ms, frame.index)
        session.record_frame(record)
        if session.is_complete():
            break

result = session.end_session(symptom_score=4)   # -> dict, JSON-serializable
```

---

## Output JSON schema

### Top level

| Field | Meaning |
|---|---|
| `schema_version` | Schema version, currently `0.1.0` |
| `test_type` | Always `"VOMS_visual_motion_subtest"` |
| `disclaimer` | Not-a-diagnosis statement. Always present. |
| `session` | Timing and configured target reps |
| `tracking_quality` | Data-quality gate — check this before trusting metrics |
| `head_motion` | Reps, amplitude, angular velocity, per-sweep detail |
| `gaze_stability` | The core VMS-relevant fixation signal |
| `self_reported_symptoms` | The 0-10 patient rating |

### `tracking_quality`

| Field | Meaning |
|---|---|
| `total_frames` / `frames_with_face` | Frame counts |
| `face_detection_rate` | 0-1. Low values mean the rest of the data is unreliable. |
| `mean_landmark_confidence` | Fraction of landmarks inside frame bounds (proxy — the Tasks API exposes no per-face score) |
| `effective_fps` | Achieved rate. MediaPipe inference, not the camera, is the limiter (~15-20 fps typical). |

### `head_motion`

Head pose comes from MediaPipe's facial transformation matrix, decomposed to Euler angles in
**degrees**. Yaw is the primary axis for this test.

| Field | Meaning |
|---|---|
| `completed_reps` | Detected reps. **1 rep = 2 sweeps** (left-right-left). |
| `total_sweeps` | One sweep = one traverse between yaw extremes |
| `reached_target_reps` | Whether the protocol rep count was met |
| `yaw_range_deg` | Total yaw excursion observed |
| `mean_/max_sweep_amplitude_deg` | Per-sweep peak-to-peak rotation |
| `mean_/max_peak_angular_velocity_dps` | Rotation speed, degrees/second |
| `pitch_range_deg` / `roll_range_deg` | Off-axis motion. Large values suggest the patient tilted or nodded instead of rotating cleanly. |
| `sweeps[]` | Per-sweep detail: timing, direction, amplitude, mean and peak velocity |
| `insufficient_data` | `true` if no qualifying sweep was found |

Sweeps below `min_sweep_amplitude_deg` (20°) are ignored so tracker jitter and small
readjustments don't inflate the rep count. An extreme is only confirmed once yaw reverses by
`reversal_deg` (8°).

### `gaze_stability` — the core signal

When someone correctly fixates a stationary target while rotating their head, their eyes
counter-rotate smoothly and proportionally against the head (vestibulo-ocular reflex). So iris
position within the eye socket should be a near-**linear function of head yaw**.

We fit that line across all moving frames. What matters is the **residual** — eye motion *not*
explained by smooth compensation, i.e. saccadic intrusions and fixation breaks.

| Field | Meaning |
|---|---|
| `moving_frames_analyzed` | Frames above the motion threshold (15°/s). Needs ≥10. |
| `compensation_slope` | Fitted eye-vs-head gain |
| `compensation_r2` | How linear the compensation was. Near 1.0 = smooth. |
| `residual_rms_offset_units` | **Primary instability metric.** RMS unexplained eye motion. Higher = worse fixation. |
| `residual_rms_deg_approx` | Same, converted to degrees — see caveat below |
| `residual_max_offset_units` | Worst single deviation |
| `iris_std_during_motion_offset_units` | Raw iris spread during motion |
| `fixation_stability_score` | Convenience 0-100, monotonic with residual. 100 = perfectly smooth. |
| `insufficient_data` | `true` if too few moving frames to fit |

**Iris offset units:** socket-normalized. `[horizontal, vertical]`, where `0,0` is the socket
center and roughly ±0.5 spans the socket. Measured in a local frame built from the eye corners,
so it rotates with the head rather than the camera — this is what separates *eye* movement from
*head* movement.

**Sign convention (load-bearing):** the two eyes' outer/temple corners sit on opposite sides of
the face midline, so measuring each eye toward its own outer corner gives the eyes *opposing*
signs during VOR — when both eyes are in fact rotating the same real-world direction. Since the
session layer averages the eyes together, that cancels the physiological signal almost exactly
and collapses `compensation_r2` toward 0 on perfectly good data. `both_iris_offsets()` in
`tracking/face_tracker.py` owns the normalization and is the single source of truth for it;
`tests/test_gaze_sign.py` pins it. Session JSON written before this was fixed has meaningless
`gaze_stability` numbers.

**Degree caveat:** `residual_rms_deg_approx` uses a fixed anatomical constant
(`NOMINAL_DEG_PER_OFFSET_UNIT = 140`), **not** a per-user calibration. Treat degree values as
indicative magnitudes. `residual_rms_offset_units` is the trustworthy figure for comparison.

### `self_reported_symptoms`

`score` is 0-10 (`null` if not provided), with `provided` as an explicit boolean and `scale` /
`prompt` recorded alongside so the number is never interpreted without its context. Currently
collected via a CLI `input()` prompt or the `--symptom-score` flag — deliberately stubbed, since
UI is out of scope for this phase.

---

## Reading the results

`face_detection_rate` and `reached_target_reps` are gates. If the face wasn't tracked reliably or
the patient didn't complete the reps, the gaze numbers describe an incomplete test — not a
finding. Check those first.

The intended future comparison is **`residual_rms_offset_units` against the self-reported symptom
score**, across sessions and against normative data. No thresholds are hardcoded, because
establishing them is a clinical validation exercise, not a coding one.

## Out of scope for this phase

No UI, no appointment booking, no diagnosis or exercise-recommendation logic, no normative
thresholds.

## Known limitations

- Gaze offset is uncalibrated; absolute degree values are approximate.
- `mean_sweep_amplitude_deg` can be pulled down by a partial first sweep if capture starts
  mid-rotation.
- Trunk rotation is not measured — only head pose is tracked, so head-vs-trunk independence
  can't be verified from this data alone.
- A single-camera face tracker can produce false-positive detections on face-like objects; treat
  `face_detection_rate` as necessary but not sufficient evidence of a valid recording.
