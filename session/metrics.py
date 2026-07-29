"""Signal processing helpers for VOMS head-rotation analysis."""
from __future__ import annotations

import numpy as np

# Converts a socket-normalized iris offset into an approximate eye rotation in
# degrees. Derived from typical anatomy (~30mm palpebral fissure, ~12mm eyeball
# radius), NOT from a per-user calibration, so degree-valued gaze outputs are
# indicative magnitudes rather than measured angles.
NOMINAL_DEG_PER_OFFSET_UNIT = 140.0


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or values.size < window:
        return values
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="same")


def angular_velocity(angles_deg: np.ndarray, times_s: np.ndarray) -> np.ndarray:
    """Central-difference derivative in degrees/second, same length as input."""
    if angles_deg.size < 2:
        return np.zeros_like(angles_deg)
    return np.gradient(angles_deg, times_s)


def find_turning_points(values: np.ndarray, times_s: np.ndarray, reversal_deg: float):
    """Hysteresis peak/valley detection.

    A candidate extreme is only confirmed once the signal reverses by
    reversal_deg, which keeps tracker jitter from registering as head reversals.
    Returns a list of (time_s, value, kind) with kind in {"max", "min"}.
    """
    if values.size == 0:
        return []

    points = []
    direction = 0
    run_max = run_min = values[0]
    run_max_t = run_min_t = times_s[0]

    for v, t in zip(values, times_s):
        if direction >= 0:
            if v > run_max:
                run_max, run_max_t = v, t
            if v < run_max - reversal_deg:
                points.append((float(run_max_t), float(run_max), "max"))
                direction = -1
                run_min, run_min_t = v, t
                continue
        if direction <= 0:
            if v < run_min:
                run_min, run_min_t = v, t
            if v > run_min + reversal_deg:
                points.append((float(run_min_t), float(run_min), "min"))
                direction = 1
                run_max, run_max_t = v, t
    return points


def build_sweeps(turning_points, times_s, yaw, velocity, min_amplitude_deg: float):
    """Pair consecutive turning points into directional head sweeps.

    Each sweep is one traverse from one extreme to the next (e.g. left->right).
    Sweeps below min_amplitude_deg are dropped as incidental motion.
    """
    sweeps = []
    for (t0, v0, k0), (t1, v1, k1) in zip(turning_points, turning_points[1:]):
        amplitude = abs(v1 - v0)
        duration = t1 - t0
        if amplitude < min_amplitude_deg or duration <= 0:
            continue

        mask = (times_s >= t0) & (times_s <= t1)
        seg_vel = velocity[mask]
        peak_vel = float(np.max(np.abs(seg_vel))) if seg_vel.size else 0.0

        sweeps.append({
            "start_s": round(t0, 3),
            "end_s": round(t1, 3),
            "duration_s": round(duration, 3),
            "direction": "toward_positive_yaw" if v1 > v0 else "toward_negative_yaw",
            "start_yaw_deg": round(float(v0), 2),
            "end_yaw_deg": round(float(v1), 2),
            "amplitude_deg": round(float(amplitude), 2),
            "mean_angular_velocity_dps": round(float(amplitude / duration), 2),
            "peak_angular_velocity_dps": round(peak_vel, 2),
        })
    return sweeps


def gaze_stability(yaw: np.ndarray, iris_h: np.ndarray, moving_mask: np.ndarray):
    """Quantify how well gaze held a fixed target while the head rotated.

    During correct performance the eyes counter-rotate smoothly against the head,
    so iris offset is a near-linear function of head yaw. We fit that line over
    the moving frames; the residual is eye motion NOT explained by smooth
    compensation (saccadic intrusion, fixation breaks), which is the VMS-relevant
    instability signal.
    """
    n_moving = int(np.count_nonzero(moving_mask))
    out = {
        "moving_frames_analyzed": n_moving,
        "compensation_slope": None,
        "compensation_r2": None,
        "residual_rms_offset_units": None,
        "residual_rms_deg_approx": None,
        "residual_max_offset_units": None,
        "iris_std_during_motion_offset_units": None,
        "fixation_stability_score": None,
        "insufficient_data": True,
    }
    if n_moving < 10:
        return out

    y = yaw[moving_mask]
    e = iris_h[moving_mask]
    if np.std(y) < 1e-6 or np.std(e) < 1e-9:
        return out

    slope, intercept = np.polyfit(y, e, 1)
    predicted = slope * y + intercept
    residual = e - predicted

    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((e - np.mean(e)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else None

    residual_rms = float(np.sqrt(np.mean(residual ** 2)))
    residual_deg = residual_rms * NOMINAL_DEG_PER_OFFSET_UNIT

    # Monotonic 0-100 convenience score: 100 = no unexplained eye motion.
    # 0.05 offset units of residual is treated as the "clearly unstable" anchor.
    score = 100.0 * float(np.exp(-residual_rms / 0.05))

    out.update({
        "compensation_slope": round(float(slope), 5),
        "compensation_r2": round(float(r2), 4) if r2 is not None else None,
        "residual_rms_offset_units": round(residual_rms, 5),
        "residual_rms_deg_approx": round(residual_deg, 2),
        "residual_max_offset_units": round(float(np.max(np.abs(residual))), 5),
        "iris_std_during_motion_offset_units": round(float(np.std(e)), 5),
        "fixation_stability_score": round(score, 1),
        "insufficient_data": False,
    })
    return out
