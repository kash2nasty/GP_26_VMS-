"""VOMS visual-motion subtest session: start_session / record_frame / end_session."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from tracking.face_tracker import FrameRecord
from . import metrics, signals

TEST_TYPE = "VOMS_visual_motion_subtest"
DISCLAIMER = (
    "This output is a screening data point only and is NOT a medical diagnosis. "
    "No condition can be diagnosed from these measurements alone. The head, eye, "
    "eyelid and facial signals recorded here are screening observations, not "
    "clinical findings. Results must be reviewed and interpreted by a qualified "
    "clinician in the context of a full clinical assessment."
)

# 0.2.0 adds the oculomotor_signals, ocular_alignment, eyelid_signals,
# head_control and facial_symmetry blocks. Everything the 0.1.0 shape carried is
# still present and unchanged, so a reader written against 0.1.0 keeps working.
SCHEMA_VERSION = "0.2.0"


@dataclass
class SessionConfig:
    target_reps: int = 5
    # A sweep must reach this amplitude to count toward a rep.
    min_sweep_amplitude_deg: float = 20.0
    # Yaw must reverse by this much before an extreme is confirmed.
    reversal_deg: float = 8.0
    # Frames above this |angular velocity| count as "head is moving".
    motion_velocity_threshold_dps: float = 15.0
    smoothing_window: int = 5
    max_duration_s: float = 120.0
    # Frames whose mean eye aperture falls below this are treated as blinks and
    # excluded from the gaze fit. During a blink the iris landmarks are unreliable
    # and can report a large spurious offset, which would inflate residual_rms.
    # Open eyes sit around 0.25-0.40; this threshold is provisional.
    min_eye_aperture_ratio: float = 0.15


@dataclass
class VOMSSession:
    config: SessionConfig = field(default_factory=SessionConfig)

    def __post_init__(self):
        self._records: list[FrameRecord] = []
        self._started_at: float | None = None
        self._ended_at: float | None = None
        self._first_ts_ms: int | None = None
        self._last_ts_ms: int | None = None
        # Memo for _analyze(), keyed on how many frames it covered. Live capture
        # asks for completed_reps() and then is_complete() after every single
        # frame, and is_complete() asks for completed_reps() again, so a naive
        # _analyze() ran three full passes over the whole session per frame. That
        # is quadratic in frame count for an answer that cannot have changed.
        self._analysis_cache: tuple[int, dict | None] | None = None

    # ---- lifecycle -------------------------------------------------------

    def start_session(self):
        self._records.clear()
        self._started_at = time.time()
        self._ended_at = None
        self._first_ts_ms = None
        self._last_ts_ms = None
        self._analysis_cache = None

    def record_frame(self, record: FrameRecord):
        if self._started_at is None:
            raise RuntimeError("start_session() must be called before record_frame()")
        self._records.append(record)
        self._analysis_cache = None
        if self._first_ts_ms is None:
            self._first_ts_ms = record.timestamp_ms
        self._last_ts_ms = record.timestamp_ms

    def end_session(self, symptom_score: int | None = None) -> dict:
        """Finalize and return the full session JSON-serializable result."""
        if self._started_at is None:
            raise RuntimeError("start_session() was never called")
        self._ended_at = time.time()
        return self._build_result(symptom_score)

    # ---- live progress ---------------------------------------------------

    def _analyze(self):
        """Derived signals from everything recorded so far, memoized per frame count."""
        if self._analysis_cache is not None and self._analysis_cache[0] == len(self._records):
            return self._analysis_cache[1]
        analysis = self._analyze_uncached()
        self._analysis_cache = (len(self._records), analysis)
        return analysis

    def _analyze_uncached(self):
        tracked = [
            r for r in self._records
            if r.face_detected and r.head_yaw is not None
        ]
        if len(tracked) < 2:
            return None

        t0 = tracked[0].timestamp_ms
        times_s = np.array([(r.timestamp_ms - t0) / 1000.0 for r in tracked])
        yaw_raw = np.array([r.head_yaw for r in tracked], dtype=float)
        yaw = metrics.moving_average(yaw_raw, self.config.smoothing_window)
        velocity = metrics.angular_velocity(yaw, times_s)

        iris_vals = []
        for r in tracked:
            offsets = [o for o in (r.left_iris_offset, r.right_iris_offset) if o]
            iris_vals.append(float(np.mean([o[0] for o in offsets])) if offsets else np.nan)
        iris_h = np.array(iris_vals, dtype=float)

        # Blink rejection. Only affects the gaze fit -- a blink does not disturb
        # head pose, so yaw/velocity keep every tracked frame.
        aperture_vals = []
        for r in tracked:
            vals = [
                a for a in (r.left_eye_aperture, r.right_eye_aperture)
                if a is not None
            ]
            aperture_vals.append(float(np.mean(vals)) if vals else np.nan)
        aperture = np.array(aperture_vals, dtype=float)

        # NaN aperture (older records with no aperture field) compares False here,
        # so an unknown aperture is never treated as a blink.
        blink = aperture < self.config.min_eye_aperture_ratio
        blinks_excluded = int(np.count_nonzero(blink & ~np.isnan(iris_h)))
        iris_h = iris_h.copy()
        iris_h[blink] = np.nan

        turning_points = metrics.find_turning_points(yaw, times_s, self.config.reversal_deg)
        sweeps = metrics.build_sweeps(
            turning_points, times_s, yaw, velocity, self.config.min_sweep_amplitude_deg
        )
        return {
            "times_s": times_s,
            "yaw": yaw,
            # Unsmoothed, for the tremor search only. The 5-sample boxcar above
            # exists to stop tracker jitter registering as a head reversal, and it
            # attenuates a 4 Hz oscillation to about 43% of its real size, so
            # measuring tremor on the smoothed trace under-reports it by more than
            # a factor of two.
            "yaw_raw": yaw_raw,
            "velocity": velocity,
            "iris_h": iris_h,
            "aperture": aperture,
            "blinks_excluded": blinks_excluded,
            "sweeps": sweeps,
            "tracked": tracked,
        }

    def completed_reps(self) -> int:
        """One rep = two sweeps (e.g. left->right->left)."""
        a = self._analyze()
        return len(a["sweeps"]) // 2 if a else 0

    def is_complete(self) -> bool:
        if self._started_at is None:
            return False
        if self.elapsed_s() >= self.config.max_duration_s:
            return True
        return self.completed_reps() >= self.config.target_reps

    def elapsed_s(self) -> float:
        if self._started_at is None:
            return 0.0
        end = self._ended_at or time.time()
        return end - self._started_at

    # ---- result assembly -------------------------------------------------

    def _build_result(self, symptom_score: int | None) -> dict:
        total_frames = len(self._records)
        detected_frames = sum(1 for r in self._records if r.face_detected)
        a = self._analyze()

        result = {
            "schema_version": SCHEMA_VERSION,
            "test_type": TEST_TYPE,
            "disclaimer": DISCLAIMER,
            "session": {
                "started_at_unix": round(self._started_at, 3),
                "ended_at_unix": round(self._ended_at, 3),
                "duration_s": round(self.elapsed_s(), 3),
                "target_reps": self.config.target_reps,
            },
            "tracking_quality": {
                "total_frames": total_frames,
                "frames_with_face": detected_frames,
                "face_detection_rate": (
                    round(detected_frames / total_frames, 4) if total_frames else 0.0
                ),
                "mean_landmark_confidence": None,
                "effective_fps": None,
            },
            "self_reported_symptoms": {
                "scale": "0-10",
                "prompt": (
                    "Symptom provocation reported by the patient immediately after the "
                    "test (0 = no symptoms, 10 = worst imaginable)."
                ),
                "score": symptom_score,
                "provided": symptom_score is not None,
            },
        }

        confidences = [
            r.landmark_confidence for r in self._records if r.landmark_confidence is not None
        ]
        if confidences:
            result["tracking_quality"]["mean_landmark_confidence"] = round(
                float(np.mean(confidences)), 4
            )
        if self.elapsed_s() > 0:
            result["tracking_quality"]["effective_fps"] = round(
                total_frames / self.elapsed_s(), 2
            )

        if a is None:
            for block in (
                "head_motion", "gaze_stability", "oculomotor_signals",
                "ocular_alignment", "eyelid_signals", "head_control",
                "facial_symmetry",
            ):
                result[block] = {"insufficient_data": True}
            return result

        sweeps = a["sweeps"]
        amplitudes = np.array([s["amplitude_deg"] for s in sweeps]) if sweeps else np.array([])
        peak_vels = (
            np.array([s["peak_angular_velocity_dps"] for s in sweeps]) if sweeps else np.array([])
        )
        durations = np.array([s["duration_s"] for s in sweeps]) if sweeps else np.array([])

        result["head_motion"] = {
            "insufficient_data": not bool(sweeps),
            "completed_reps": len(sweeps) // 2,
            "total_sweeps": len(sweeps),
            "reached_target_reps": (len(sweeps) // 2) >= self.config.target_reps,
            "yaw_range_deg": round(float(np.max(a["yaw"]) - np.min(a["yaw"])), 2),
            "mean_sweep_amplitude_deg": (
                round(float(np.mean(amplitudes)), 2) if amplitudes.size else None
            ),
            "max_sweep_amplitude_deg": (
                round(float(np.max(amplitudes)), 2) if amplitudes.size else None
            ),
            "mean_peak_angular_velocity_dps": (
                round(float(np.mean(peak_vels)), 2) if peak_vels.size else None
            ),
            "max_peak_angular_velocity_dps": (
                round(float(np.max(peak_vels)), 2) if peak_vels.size else None
            ),
            # Sweep pace. Needed to compare against the protocol's metronome
            # cadence and to judge whether pace held steady within the session --
            # a varying pace contaminates the gaze residual.
            "mean_sweep_duration_s": (
                round(float(np.mean(durations)), 3) if durations.size else None
            ),
            "sweep_duration_cv": (
                round(float(np.std(durations) / np.mean(durations)), 4)
                if durations.size and np.mean(durations) > 1e-9 else None
            ),
            "pitch_range_deg": self._range_of("head_pitch", a["tracked"]),
            "roll_range_deg": self._range_of("head_roll", a["tracked"]),
            "sweeps": sweeps,
        }

        valid_iris = ~np.isnan(a["iris_h"])
        moving = (np.abs(a["velocity"]) > self.config.motion_velocity_threshold_dps) & valid_iris
        result["gaze_stability"] = metrics.gaze_stability(a["yaw"], a["iris_h"], moving)
        result["gaze_stability"]["frames_excluded_blink"] = a["blinks_excluded"]
        result["gaze_stability"]["min_eye_aperture_ratio"] = (
            self.config.min_eye_aperture_ratio
        )
        result["gaze_stability"]["metric_notes"] = (
            "compensation_slope/r2 describe how linearly the eyes counter-rotated "
            "against head yaw. residual_* captures eye motion not explained by that "
            "smooth compensation and is the primary instability signal. Degree values "
            "use an uncalibrated anatomical constant and are approximate. Frames "
            "where the eyes were closed are excluded from the fit; see "
            "frames_excluded_blink."
        )

        # ---- the wider signal set -----------------------------------------
        #
        # These read the same frames from a different angle. They are appended
        # rather than folded into the blocks above so that a reader written
        # against schema 0.1.0 sees exactly what it saw before, and so that a
        # failure to interpret one of them can never affect the VOMS result the
        # capture was actually run for.
        blink_threshold = self.config.min_eye_aperture_ratio
        result["oculomotor_signals"] = signals.oculomotor_signals(
            a["times_s"], a["yaw"], a["iris_h"], a["aperture"], moving, blink_threshold
        )
        result["ocular_alignment"] = signals.ocular_alignment(
            a["tracked"], a["aperture"], blink_threshold
        )
        result["eyelid_signals"] = signals.eyelid_signals(
            a["times_s"], a["tracked"], a["aperture"], blink_threshold
        )
        result["head_control"] = signals.head_control(
            a["times_s"], a["yaw"], a["iris_h"], moving,
            sweeps, result["head_motion"], a["yaw_raw"],
        )
        result["facial_symmetry"] = signals.facial_symmetry(a["tracked"])
        return result

    @staticmethod
    def _range_of(attr: str, tracked) -> float | None:
        vals = [getattr(r, attr) for r in tracked if getattr(r, attr) is not None]
        return round(float(max(vals) - min(vals)), 2) if len(vals) >= 2 else None
