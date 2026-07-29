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
scoring/severity.py        Composite screening severity tiers
scoring/exercises.py       Tier -> Cawthorne-Cooksey exercise mapping
scoring/protocol.py        Protocol-fidelity assessment vs standardized VOMS
scoring/pipeline.py        enrich_session() -- shared by both entrypoints
api/repository.py          Session discovery/loading for the API (no FastAPI import)
api/main.py                FastAPI read-only endpoints over sessions/
api/capture.py             WebSocket endpoint for browser-driven capture
session_io.py              Session file naming/writing, shared by CLI and API
web/                       Next.js dashboard (see "Results dashboard" below)
run_session.py             CLI entrypoint (capture, optionally scored)
score_session.py           CLI entrypoint (re-score an existing session JSON)
check_yaw_ceiling.py       Measures the yaw angle where tracking degrades
tests/test_gaze_sign.py    Regression tests for the iris sign convention
tests/test_blink_rejection.py  Blink detection and exclusion from the gaze fit
tests/test_scoring.py      Tier, gate, fidelity and exercise-mapping tests
tests/test_api.py          API loading, edge shapes, and the no-mediapipe constraint
tests/test_capture.py      Capture socket end-to-end through real MediaPipe
models/                    face_landmarker.task
sessions/                  Saved session JSON
```

### Tests

Plain asserts, no pytest required:

```powershell
python tests/test_gaze_sign.py
python tests/test_blink_rejection.py
python tests/test_scoring.py
python tests/test_api.py
python tests/test_capture.py     # slower: real MediaPipe over the capture socket
```

These suites are mutation-tested: each threshold, gate and safety rule has a corresponding
deliberate break that must turn them red. Two tests were found decorative that way and
rewritten — a blink test that checked a reported count rather than actual exclusion, and a tier
test whose fixture used symptom score 0, which multiplies the symptom weight away. If you retune
a threshold, re-run that check rather than trusting a green suite.

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

---

## Screening severity and exercise suggestions

A second layer turns a captured session into a coarse severity tier plus general published
exercise suggestions. It is a **screening** layer: it does not identify, confirm, or rule out
any condition, and every block it emits carries its own disclaimer and safety note.

```powershell
python score_session.py sessions/session_20260729T024816Z.json   # re-score an existing file
python score_session.py sessions/*.json                          # batch
python score_session.py sessions/s.json --stdout                 # print, don't write
python run_session.py --score                                    # capture and score in one go
```

`score_session.py` writes `<name>.scored.json` beside the original and never modifies the
input, so re-scoring old captures with updated thresholds is safe. Both entrypoints call the
same `scoring.pipeline.enrich_session()`, so a live run and a later re-score cannot disagree.

### The severity formula

```
symptom_component     = symptom_score * 10              -> 0..100
instability_component = 100 - fixation_stability_score   -> 0..100
composite             = 0.60 * symptom_component + 0.40 * instability_component

composite <  20 -> minimal     40 <= c < 65 -> moderate
20 <= c   <  40 -> mild        65 <= c      -> pronounced
```

**Floor rule:** a symptom score ≥ 2 is never reported as `minimal`. Mucha et al. (2014)
established ≥ 2 on any VOMS item as a positive screening cut-off, so `minimal` there would
contradict the published anchor.

**Calibration status — read before trusting the numbers.** The symptom cut-off is published.
Nothing on the objective side is: `fixation_stability_score` is bespoke to this tool and built
on an arbitrary internal anchor, and degree values use an uncalibrated constant. The 0.60/0.40
split reflects that asymmetry in evidence — the validated signal carries more weight — but the
weights are a judgement call, not a fitted result. The formula is emitted in the output's
`method` block, generated from the constants so it cannot drift from what was applied.

### Data-quality gates

The objective signal is only used if `face_detection_rate ≥ 0.75`, `compensation_r2 ≥ 0.50`,
and `completed_reps ≥ 3`. Failing any gate drops to `status: symptom_only` with the failed
gates listed — never a silent fallback. If neither input is usable, `status:
insufficient_data`, `severity_tier: null`, and **no exercises are suggested at all**.

A caveat kept in the open: low `compensation_r2` is ambiguous. It can mean the tracker failed
*or* that the patient genuinely didn't fixate — which would be real signal, and arguably the
most interesting finding available. Gating on it is the conservative choice; the cost is that a
genuine severe fixation failure reads as "not usable" rather than "pronounced". Separating the
two needs a second modality this phase doesn't have.

### Protocol fidelity

The gaze metric is computed over whatever head motion actually occurred, which says nothing
about whether that motion resembled the test the metric is meant to characterise. Every scored
session therefore carries a `protocol_fidelity` block comparing observed motion against the
standardized VOMS visual-motion parameters:

| | reference | source |
|---|---|---|
| amplitude | 80° each side → **160° per sweep** | Mucha et al. 2014 |
| pace | **50 bpm**, one beat per direction → 1.2 s per sweep | Mucha et al. 2014 |
| reps | 5 | Mucha et al. 2014 |

Deviations are reported as `advisory_flags` and surfaced in `notes`, with
`comparable_to_clinical_protocol` stating plainly whether the session can be read against
published norms. Flags cover amplitude, pace, within-session pace consistency
(`sweep_duration_cv`), off-axis roll/pitch, and rep count.

**Why advisory rather than blocking.** A single front-facing webcam may not be able to track
±80° of yaw at all — the face approaches profile and the landmarker degrades. Until that ceiling
is measured, hard-gating on protocol amplitude would mark every session unusable and discard the
objective signal entirely. Flip `ENFORCE_AS_GATES = True` in `scoring/protocol.py` to promote
them to blocking gates once the reachable amplitude is known.

Note also that the Euler decomposition in `face_tracker.py` couples axes at large yaw, so part
of a high `roll_range_deg` may be decomposition artifact rather than genuine head tilt — another
reason these flag rather than block.

Sessions captured before the aggregate pace fields existed still have `sweeps[]`, so pace is
recovered from there and marked `pace_derived_from_sweeps: true`.

### Measuring the yaw ceiling

```powershell
python check_yaw_ceiling.py --preview
```

Rotate progressively wider, holding briefly at each extreme. Reports tracking quality binned by
|yaw| so you can see where detection falls away from ~1.0, and whether ±80° is reachable at all.
If it isn't, protocol-faithful capture is impossible with this hardware and that belongs in the
limitations list rather than being rediscovered later.

### Blink rejection

During a blink the iris landmarks are unreliable and can report a large spurious offset, which
`_iris_offset()` cannot distinguish from a genuine gaze deviation. Left in, a blink inflates
`residual_rms` → lowers `fixation_stability_score` → raises the tier. A ~20 s capture at a normal
blink rate contains roughly 5–7 blinks, so this is the common case rather than an edge case.

`face_tracker.py` reports a per-eye aperture ratio (vertical opening ÷ eye width; open ≈ 0.25–0.40,
collapsing toward 0 when shut). Frames below `min_eye_aperture_ratio` (0.15, provisional) are
excluded from the gaze fit only — head pose keeps every tracked frame, since a blink doesn't
disturb head rotation. The count appears as `frames_excluded_blink`; `null` means the session
predates the field, which is not the same as zero.

### Why higher severity gets fewer exercises

This inverts the naive mapping, deliberately. Habituation works by repeated exposure at a
tolerable intensity, so a more-provoked result yields a **shorter, gentler** starting set
(seated, eyes open, brief) while a less-provoked result starts nearer the dynamic end of the
protocol. At `pronounced`, sustained head rotation — the movement the subtest uses to provoke
symptoms — is withheld from the starting set pending clinician review. A tier→difficulty
mapping would have handed the most symptomatic person the most aggressive protocol.

Exercises come from the published Cawthorne-Cooksey protocol (Cawthorne 1946; Cooksey 1946),
with descriptions and frequency norms drawn from patient-facing renderings of it. The catalogue
lives in one dict in `scoring/exercises.py` with the tier mapping beside it, so it is reviewable
and editable without touching logic.

---

## Results dashboard (API + web frontend)

A read-only dashboard for browsing past sessions. Two processes: a FastAPI backend that
reads `sessions/`, and a Next.js frontend that renders it.

### Running it

You need **two terminals**, both from the project root.

**Terminal 1 — the API:**

```powershell
.venv\Scripts\activate
uvicorn api.main:app --reload --port 8000
```

Check it with http://127.0.0.1:8000/docs (an interactive view of the endpoints, generated
automatically by FastAPI).

**Terminal 2 — the frontend:**

```powershell
cd web
npm run dev
```

Then open **http://localhost:3000**. If the API isn't running, the page says so and shows
the command to start it rather than failing with a blank screen.

### Architecture

```
api/repository.py    Finds and loads session JSON. No FastAPI import, so it unit-tests directly.
api/main.py          FastAPI app: GET /sessions, GET /sessions/{id}, GET /health.
api/capture.py       WebSocket capture from the browser (see below).
session_io.py        Where a session gets written. Shared by the CLI and the API.
web/                 Next.js 16 + Tailwind 4 + shadcn/ui (dashboard-01 block).
```

The API **never touches the camera stack.** `session/voms_session.py` looks like the natural
place to import the canonical disclaimer from, but it pulls in `tracking/face_tracker.py` →
`mediapipe`, dragging the whole capture stack into the web process. Disclaimers come from
`scoring/` (import-clean) and from the session JSON instead. `tests/test_api.py` enforces this
in a subprocess — if someone adds a convenient import, that test fails.

### What the API does with the three on-disk shapes

`sessions/` is not uniform, because `run_session.py` changed over time. A *session* is the
logical unit keyed by timestamp, not a file:

| On disk | Served as | `scoring_source` |
|---|---|---|
| raw + `.scored.json` pair | the stored score | `file` |
| `.scored.json` only (older `--score` run) | the stored score | `file` |
| raw only (no `--score`) | scored in memory on read | `computed` |

Stale scores are served **as-is**, not re-scored. A file written by scoring schema 0.1.0 has no
`protocol_fidelity`; re-scoring it on read would make the API disagree with the file on disk,
and this phase is read-only. The UI shows those as "Not assessed" — distinct from "off
protocol", because a check that never ran is not a check that failed.

A malformed file is reported in an `unreadable` list rather than taking down the whole page or
silently vanishing.

### Disclaimers are served, not hardcoded

Every response carrying results includes a `disclaimers` block, and the frontend renders that
text rather than its own copy. The Python layer deliberately bakes disclaimers into its output
schema so a later UI cannot drop them; duplicating the wording in TypeScript would defeat that
by letting the two drift. On the detail page the exercise disclaimer and safety note render
**above** the exercises, since that's the one screen telling someone to do physical activity.

### Running the test from the browser

**Sessions → New session**, or http://localhost:3000/capture.

The browser is a camera and a display. It grabs JPEG frames from the webcam, streams them to
Python over a WebSocket, and renders the progress Python sends back. **No analysis happens in
JavaScript.** Every number still comes from `tracking/`, `session/` and `scoring/` — the same
code the CLI runs.

That was the central decision, and it was not about convenience. Porting the metrics to
TypeScript would mean a second implementation of the iris sign convention, blink rejection,
sweep detection, the gaze fit and the scoring thresholds — all covered by a Python test suite
that exists *because* a sign-convention bug in exactly that math silently destroyed the core
signal once already. Two copies would reintroduce that class of bug with nothing to catch the
drift.

**Frames, not a video upload.** MediaRecorder produces WebM/VP8-9, and OpenCV's Windows build
can't be relied on to decode it. JPEG frames go through `cv2.imdecode`, which is unconditionally
supported, and they allow live rep counting *during* the test rather than only after.

**MediaPipe is imported lazily**, inside the capture handler. `import api.main` still pulls in
zero camera-stack modules even with the capture router mounted, so the read-only browsing
endpoints keep their fast startup — and `tests/test_api.py` still enforces that unchanged.

**The pacing metronome is audible, not just visual.** The patient is meant to be staring at
their own thumb, so an on-screen-only cue would be invisible exactly when it matters. High tone
means turn left, low tone right, at the protocol's 50 bpm. This is a correctness feature: pace is
what this project found it was getting wrong, and uncontrolled rotation speed is what makes
sessions incomparable. The panel also shows widest-turn-so-far against the 80° target.

**The preview is mirrored; the captured frames are not.** Mirroring the pixels sent to Python
would invert head yaw and swap which eye is which — the same left/right confusion that caused
the original bug. The mirror is a CSS transform on the `<video>` element only; the canvas draws
from the unmirrored source.

**Nothing is written until you choose to save.** Closing the tab, disconnecting, or pressing
Discard writes no file. Saving a session the user walked away from would litter the dashboard
with records nobody chose to keep. A capture that *is* saved writes both the raw and scored
files, exactly like `run_session.py --score`, via the shared `session_io.save_session`.

Frames are timestamped on arrival by the server's monotonic clock rather than by the browser.
Over loopback that difference is sub-millisecond, and the metrics already use real timestamps
rather than assuming a fixed rate — but it does mean a stalled tab reads as slow head motion
rather than as dropped frames.

### Notes on the frontend

Built from the shadcn `dashboard-01` block via the CLI, with deliberate departures:

- **The block's `data-table.tsx` was replaced.** Its 874 lines implement drag-to-reorder and
  row-selection over a `{header, reviewer, target}` document schema. On immutable capture
  records, a drag handle is an affordance the app can't honour. The replacement keeps the same
  TanStack Table + shadcn primitives (so it matches visually) and keeps column sorting, which
  is genuinely useful and server-free. Tier sorting uses clinical order, not alphabetical.
- **No cross-session trend chart.** The block's chart was demo data. A trend of the composite
  score would contradict this project's own finding that the objective half is uncalibrated and
  sensitive to uncontrolled rotation speed — it would look like a measurement while being an
  artifact of inconsistent technique. Symptom score alone would be a defensible future addition.
- **Sidebar and user menu stripped.** There's no authentication in this phase, so an avatar
  would imply a login that doesn't exist, and placeholder nav links teach that things are
  clickable when they aren't.
- **Tier colours are not a red/green scale.** These are screening bands, not pass/fail; a green
  "minimal" badge would read as an all-clear this tool cannot support.
- **Theme is a light-blue tint, not a wash.** Chroma is kept to 0.01–0.04 on surfaces so large
  areas stay readable and don't compete with the amber/rose status badges, which carry actual
  meaning. Headings are Source Serif 4 against Inter body copy. Contrast was measured rather
  than eyeballed: light `muted-foreground` (the smallest text on the page) is 5.95:1, dark is
  7.64:1, both past WCAG AA.

Two version-specific gotchas worth knowing if you edit this code:

- **Next.js 16 removed synchronous `params`.** Dynamic pages must `await params`. See
  `web/AGENTS.md` — that version has breaking changes, and the bundled docs in
  `web/node_modules/next/dist/docs/` are the authority.
- **This shadcn build is on Base UI, not Radix.** Composition uses `render={<Link/>}`, not
  `asChild`. Using `asChild` typechecks as an error rather than failing at runtime.

`npm audit` reports 12 high-severity advisories, all in build tooling (eslint → minimatch,
postcss, sharp) reachable only at lint/build time, not by this read-only local dashboard. No
semver-compatible fix exists; `npm audit fix --force` would break major versions for no real
gain here.

## Out of scope

No accounts or authentication, no editing or deleting sessions from the UI, no appointment
booking, no normative/validated thresholds, and no clinical interpretation — screening signal
and general exercise suggestions only.

Browser capture is intentionally *not* independent of Python: the frontend cannot score a
session on its own, and is useless without the local API running. That is the point — one
implementation of the metrics, not two.

## Known limitations

- Gaze offset is uncalibrated; absolute degree values are approximate.
- `mean_sweep_amplitude_deg` can be pulled down by a partial first sweep if capture starts
  mid-rotation.
- Trunk rotation is not measured — only head pose is tracked, so head-vs-trunk independence
  can't be verified from this data alone.
- A single-camera face tracker can produce false-positive detections on face-like objects; treat
  `face_detection_rate` as necessary but not sufficient evidence of a valid recording.
