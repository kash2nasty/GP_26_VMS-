"""Signal processing helpers for VOMS head-rotation analysis."""
from __future__ import annotations

import numpy as np

# Converts a socket-normalized iris offset into an approximate eye rotation in
# degrees. Derived from typical anatomy (~30mm palpebral fissure, ~12mm eyeball
# radius), NOT from a per-user calibration, so degree-valued gaze outputs are
# indicative magnitudes rather than measured angles.
NOMINAL_DEG_PER_OFFSET_UNIT = 140.0


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    """Box-car smoothing that does not corrupt the ends of the signal.

    The obvious np.convolve(values, kernel, mode="same") pads with implicit zeros,
    so the first and last window/2 samples get averaged against zero. On yaw in
    degrees that is not a rounding difference: a session starting at -40 deg had
    its first samples dragged toward -24, which shrank yaw_range_deg and moved the
    first turning point. Replicating the edge values keeps the ends honest.
    """
    if window <= 1 or values.size < window:
        return values
    lead = window // 2
    padded = np.pad(values, (lead, window - 1 - lead), mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(padded, kernel, mode="valid")


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


def fit_compensation(yaw: np.ndarray, iris: np.ndarray):
    """Least-squares fit of iris offset against head yaw.

    Returns (slope, intercept, residual, r2) or None when the inputs cannot
    support a fit. Shared by gaze_stability() and by signals.py, which needs the
    residual time series itself rather than only its summary statistics: pulling
    the fit out here is what stops the two from drifting into different lines.
    """
    if yaw.size < 2 or yaw.size != iris.size:
        return None
    if np.std(yaw) < 1e-6 or np.std(iris) < 1e-9:
        return None

    slope, intercept = np.polyfit(yaw, iris, 1)
    residual = iris - (slope * yaw + intercept)

    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((iris - np.mean(iris)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else None
    return float(slope), float(intercept), residual, r2


class Oscillation:
    """Result of dominant_frequency(). Every field may be None."""

    __slots__ = ("frequency_hz", "rhythmicity", "sample_rate_hz", "amplitude_rms")

    def __init__(self, frequency_hz=None, rhythmicity=None,
                 sample_rate_hz=None, amplitude_rms=None):
        self.frequency_hz = frequency_hz
        self.rhythmicity = rhythmicity
        self.sample_rate_hz = sample_rate_hz
        self.amplitude_rms = amplitude_rms


def dominant_frequency(values: np.ndarray, times_s: np.ndarray, band) -> Oscillation:
    """Strongest oscillation in `values` inside `band`, and how rhythmic it is.

    `rhythmicity` is the share of in-band spectral power sitting in the peak bin
    and the bin either side of it. A pure sine reads near 1.0; broadband noise with
    no periodicity reads near the ratio of three bins to the number of bins in the
    band, which is small. `amplitude_rms` is the RMS of just that peak component,
    in the same units as `values`.

    WHY A UNIFORM RESAMPLE FIRST
        Frames arrive at whatever rate the camera and the landmarker managed, and
        an FFT of unevenly sampled data reports frequencies that are artifacts of
        the sampling. Resampling onto a uniform grid at the mean observed rate is
        the cheap correct-enough fix at these sample counts.

    WHY THE AMPLITUDE IS NOT JUST THE STANDARD DEVIATION OF THE INPUT
        It was, and it was wrong. The head-tremor caller feeds in a high-passed
        yaw trace, and boxcar high-passing a smooth 0.3 Hz head sweep of 40 degrees
        leaves about 0.7 degrees of residual behind. Reading the standard deviation
        of that reported a 2 degree tremor on a perfectly smooth sweep, which is
        the whole measurement inverted. Isolating the peak bins and reconstructing
        only those gives an amplitude that belongs to the oscillation rather than
        to whatever else survived the filter.

    Fields come back None when the series is too short, too slow, or flat. The
    caller is expected to check the sample rate against the band: a 15 fps capture
    cannot see anything above 7.5 Hz at all, and in practice needs several samples
    per cycle to see it well.
    """
    low, high = band
    if values.size < 16 or times_s.size != values.size:
        return Oscillation()

    span = float(times_s[-1] - times_s[0])
    if span <= 0:
        return Oscillation()
    sample_rate = round((values.size - 1) / span, 2)

    # At least three full cycles of the slowest frequency of interest, otherwise
    # the peak is indistinguishable from a trend.
    if span < 3.0 / max(low, 1e-6):
        return Oscillation(sample_rate_hz=sample_rate)
    if sample_rate < 2.0 * high:
        return Oscillation(sample_rate_hz=sample_rate)

    grid = np.linspace(times_s[0], times_s[-1], values.size)
    resampled = np.interp(grid, times_s, values)
    resampled = resampled - np.mean(resampled)
    if np.std(resampled) < 1e-12:
        return Oscillation(sample_rate_hz=sample_rate)

    # Hann window for locating the peak: without it the rectangular edges leak
    # power across the whole spectrum and a slow drift shows up as a fake peak.
    spectrum = np.abs(np.fft.rfft(resampled * np.hanning(resampled.size))) ** 2
    freqs = np.fft.rfftfreq(resampled.size, d=1.0 / sample_rate)

    band_indices = np.flatnonzero((freqs >= low) & (freqs <= high))
    if band_indices.size == 0:
        return Oscillation(sample_rate_hz=sample_rate)

    band_power = float(np.sum(spectrum[band_indices]))
    if band_power <= 1e-20:
        return Oscillation(sample_rate_hz=sample_rate)

    peak = int(band_indices[int(np.argmax(spectrum[band_indices]))])
    lo = max(int(band_indices[0]), peak - 1)
    hi = min(int(band_indices[-1]), peak + 1)
    peak_power = float(np.sum(spectrum[lo:hi + 1]))

    # Amplitude from an unwindowed reconstruction of the peak bins only, so the
    # figure is not scaled by the window and not contaminated by the rest of the
    # band.
    unwindowed = np.fft.rfft(resampled)
    isolated = np.zeros_like(unwindowed)
    isolated[lo:hi + 1] = unwindowed[lo:hi + 1]
    component = np.fft.irfft(isolated, n=resampled.size)

    return Oscillation(
        frequency_hz=round(float(freqs[peak]), 3),
        rhythmicity=round(peak_power / band_power, 4),
        sample_rate_hz=sample_rate,
        amplitude_rms=round(float(np.std(component)), 5),
    )


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
    fit = fit_compensation(y, e)
    if fit is None:
        return out
    slope, _intercept, residual, r2 = fit

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
