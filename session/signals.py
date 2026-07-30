"""Additional per-frame signals derived from the same capture as the VOMS subtest.

WHY THIS MODULE EXISTS
    The original pipeline extracted exactly what the VOMS visual-motion subtest
    needs: how well gaze held a target while the head rotated. But the capture
    already contains far more than that. Every frame carries head pose on three
    axes, both irises located inside their own sockets, both eyelid apertures, and
    the resting geometry of the mouth and brows. Those are the raw ingredients of
    several other well-described clinical signs, and throwing them away meant the
    tool could only ever say one thing about a person.

    So this module turns the same frames into five further measurement blocks.
    scoring/indications.py is what interprets them. The split is deliberate and
    matches the rest of the project: this file measures and never judges, and the
    scoring layer judges and never measures.

WHAT THIS MODULE IS NOT
    None of these numbers is a diagnosis, and none of them has been validated
    against a reference instrument. Several are bounded by the hardware in ways
    that cannot be engineered away here, and each block says so in its own
    metric_notes rather than leaving the reader to discover it:

    SAMPLING RATE      A browser capture runs near 15 fps and the CLI near 30. Any
                       oscillation faster than half that rate is invisible, and an
                       oscillation needs several samples per cycle to be measured
                       rather than merely detected. Nystagmus and head tremor both
                       live near that ceiling, which is why both report the sample
                       rate they were computed at.
    NO CALIBRATION     Iris offsets are normalised by socket size, not by a
                       per-person calibration, so interocular differences carry an
                       unknown constant bias from the landmark model itself. Only
                       large disparities mean anything.
    TASK NOT REST      This is a provocation test, not a resting observation.
                       Blink rate in particular drops during any demanding visual
                       task, so the resting norms in the literature do not
                       transfer directly.
"""
from __future__ import annotations

import numpy as np

from . import metrics

# ---- thresholds, all provisional -----------------------------------------

# A residual excursion this far from smooth compensation is counted as one
# fixation break. 0.02 socket-normalised units is roughly 3 degrees of eye
# rotation under the nominal constant in metrics.py.
SACCADE_RESIDUAL_THRESHOLD = 0.02

# Frequency bands searched for rhythmic signals. Both sit under the Nyquist limit
# of a 15 fps capture, which is the binding constraint rather than physiology:
# vestibular nystagmus and essential head tremor both extend above these bands.
NYSTAGMUS_BAND_HZ = (1.0, 5.0)
TREMOR_BAND_HZ = (2.5, 6.0)

# Window used to high-pass the yaw trace before looking for tremor. The head
# sweeps of the subtest take about 1.2 s, so smoothing over half a second removes
# the intended movement and leaves any fast oscillation riding on it.
#
# A boxcar is not a clean filter: its passband ripples, so the amplitude it hands
# through varies by roughly a quarter across the tremor band depending on where in
# the band the oscillation sits. That is accepted here rather than engineered
# around, because the threshold it feeds is provisional to begin with and a
# quarter of an arbitrary threshold is not the limiting uncertainty.
TREMOR_HIGHPASS_WINDOW_S = 0.5

# Fraction of the session used for the fatigue comparison at each end.
FATIGUE_WINDOW_SHARE = 1.0 / 3.0
MIN_SESSION_S_FOR_FATIGUE = 20.0


def _round(value, digits=5):
    if value is None:
        return None
    value = float(value)
    if not np.isfinite(value):
        return None
    return round(value, digits)


def _median(values):
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.median(values)) if values else None


def _runs(mask: np.ndarray):
    """Start and end indices of each contiguous True run in a boolean array."""
    if mask.size == 0:
        return []
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    edges = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    return list(zip(starts.tolist(), ends.tolist()))


def _per_eye(tracked, attr, component):
    """Per-frame component of a two-element per-eye field, NaN where missing."""
    out = []
    for record in tracked:
        value = getattr(record, attr, None)
        if isinstance(value, (list, tuple)) and len(value) > component:
            element = value[component]
            out.append(float(element) if element is not None else np.nan)
        else:
            out.append(np.nan)
    return np.array(out, dtype=float)


def _attr_series(tracked, attr):
    out = []
    for record in tracked:
        value = getattr(record, attr, None)
        out.append(float(value) if isinstance(value, (int, float)) else np.nan)
    return np.array(out, dtype=float)


# ---- residual reconstruction ---------------------------------------------

def compensation_residual(yaw: np.ndarray, iris_h: np.ndarray, moving_mask: np.ndarray):
    """Residual eye motion for EVERY valid frame, from a fit over moving frames.

    gaze_stability() fits the same line but only ever looks at the residual on the
    moving frames, because that is where compensation is being tested. The
    frequency analysis here needs a time series without holes: the moving frames
    exclude every direction reversal, and a series with a gap at every reversal
    has a strong artificial periodicity at exactly the sweep rate, which would be
    read as nystagmus. Fitting on the moving frames and evaluating everywhere
    keeps the fit meaningful and the time base continuous.

    Returns (residual, valid_mask) with residual NaN wherever iris data is
    missing, or None when no fit was possible.
    """
    valid = np.isfinite(iris_h) & np.isfinite(yaw)
    usable = moving_mask & valid
    if int(np.count_nonzero(usable)) < 10:
        return None

    fit = metrics.fit_compensation(yaw[usable], iris_h[usable])
    if fit is None:
        return None
    slope, intercept, _residual, _r2 = fit

    residual = np.full(iris_h.shape, np.nan, dtype=float)
    residual[valid] = iris_h[valid] - (slope * yaw[valid] + intercept)
    return residual, valid


# ---- blocks ---------------------------------------------------------------

def oculomotor_signals(times_s, yaw, iris_h, aperture, moving_mask, blink_threshold):
    """Blink behaviour, fixation breaks, and rhythmic eye oscillation."""
    out = {
        "insufficient_data": True,
        "frames_analyzed": 0,
        "blink_count": None,
        "blink_rate_per_min": None,
        "mean_blink_duration_s": None,
        "fixation_break_count": None,
        "fixation_break_rate_per_s": None,
        "largest_fixation_break_offset_units": None,
        "oscillation_frequency_hz": None,
        "oscillation_rhythmicity": None,
        "oscillation_amplitude_offset_units": None,
        "sample_rate_hz": None,
        "oscillation_band_hz": list(NYSTAGMUS_BAND_HZ),
        "metric_notes": (
            "Blink rate is measured during a provocation task, not at rest, so the "
            "resting norms in the literature do not transfer directly. A fixation "
            "break is an excursion of more than "
            f"{SACCADE_RESIDUAL_THRESHOLD} socket-normalised units away from smooth "
            "compensation. The oscillation search is bounded by the capture frame "
            "rate, not by physiology: anything above half the reported sample rate "
            "is invisible, so a null result is not evidence of absence."
        ),
    }

    span_s = float(times_s[-1] - times_s[0]) if times_s.size >= 2 else 0.0
    if span_s <= 0:
        return out
    out["frames_analyzed"] = int(times_s.size)

    # ---- blinks. Counted as events, not frames: a 3-frame blink is one blink.
    known_aperture = np.isfinite(aperture)
    if np.any(known_aperture):
        closed = known_aperture & (aperture < blink_threshold)
        events = _runs(closed)
        durations = [
            float(times_s[end] - times_s[start])
            for start, end in events
            if end > start
        ]
        out["blink_count"] = len(events)
        out["blink_rate_per_min"] = _round(len(events) / (span_s / 60.0), 2)
        out["mean_blink_duration_s"] = _round(_median(durations), 3)
        out["insufficient_data"] = False

    # ---- fixation breaks and oscillation, both off the compensation residual.
    reconstructed = compensation_residual(yaw, iris_h, moving_mask)
    if reconstructed is not None:
        residual, valid = reconstructed
        above = np.isfinite(residual) & (np.abs(residual) > SACCADE_RESIDUAL_THRESHOLD)
        breaks = _runs(above)
        out["fixation_break_count"] = len(breaks)
        out["fixation_break_rate_per_s"] = _round(len(breaks) / span_s, 3)
        out["largest_fixation_break_offset_units"] = _round(
            np.nanmax(np.abs(residual)) if np.any(np.isfinite(residual)) else None
        )

        # Frequency analysis needs a gap-free series, so interpolate across the
        # frames where the iris could not be located rather than dropping them.
        if int(np.count_nonzero(valid)) >= 16:
            filled = np.interp(times_s, times_s[valid], residual[valid])
            found = metrics.dominant_frequency(filled, times_s, NYSTAGMUS_BAND_HZ)
            out["oscillation_frequency_hz"] = found.frequency_hz
            out["oscillation_rhythmicity"] = found.rhythmicity
            out["sample_rate_hz"] = found.sample_rate_hz
            out["oscillation_amplitude_offset_units"] = found.amplitude_rms
        out["insufficient_data"] = False

    return out


def ocular_alignment(tracked, aperture, blink_threshold):
    """Horizontal and vertical difference between where the two eyes point.

    A sustained horizontal difference is the signature of a horizontal tropia; a
    sustained VERTICAL difference is the more interesting of the two, because
    vertical misalignment is a central sign rather than a refractive one.

    THE BIAS THAT CANNOT BE REMOVED HERE
        Each iris offset is normalised inside its own socket, and the landmark
        model does not place the two sockets with identical accuracy. So a
        perfectly aligned person still produces a small non-zero mean disparity,
        and that constant is indistinguishable from a small real deviation without
        a per-person calibration this tool does not have. The variability of the
        disparity is not affected by a constant bias, which is why it is reported
        alongside the mean.
    """
    out = {
        "insufficient_data": True,
        "frames_analyzed": 0,
        "horizontal_disparity_mean_offset_units": None,
        "horizontal_disparity_std_offset_units": None,
        "vertical_disparity_mean_offset_units": None,
        "vertical_disparity_std_offset_units": None,
        "vertical_disparity_max_offset_units": None,
        "metric_notes": (
            "Disparity is the right eye's offset minus the left eye's, both in "
            "socket-normalised units under the shared sign convention in "
            "tracking/face_tracker.py. An uncalibrated constant bias from the "
            "landmark model is included in the mean and cannot be separated from a "
            "small real deviation, so only large values mean anything. The standard "
            "deviation is free of that bias and describes how steadily the two eyes "
            "held the same target."
        ),
    }

    left_h = _per_eye(tracked, "left_iris_offset", 0)
    right_h = _per_eye(tracked, "right_iris_offset", 0)
    left_v = _per_eye(tracked, "left_iris_offset", 1)
    right_v = _per_eye(tracked, "right_iris_offset", 1)

    open_eyes = ~(np.isfinite(aperture) & (aperture < blink_threshold))
    usable = np.isfinite(left_h) & np.isfinite(right_h) & open_eyes
    if int(np.count_nonzero(usable)) < 10:
        return out

    horizontal = right_h[usable] - left_h[usable]
    out.update({
        "insufficient_data": False,
        "frames_analyzed": int(np.count_nonzero(usable)),
        "horizontal_disparity_mean_offset_units": _round(np.mean(horizontal)),
        "horizontal_disparity_std_offset_units": _round(np.std(horizontal)),
    })

    usable_v = np.isfinite(left_v) & np.isfinite(right_v) & open_eyes
    if int(np.count_nonzero(usable_v)) >= 10:
        vertical = right_v[usable_v] - left_v[usable_v]
        out.update({
            "vertical_disparity_mean_offset_units": _round(np.mean(vertical)),
            "vertical_disparity_std_offset_units": _round(np.std(vertical)),
            "vertical_disparity_max_offset_units": _round(
                np.max(np.abs(vertical))
            ),
        })
    return out


def eyelid_signals(times_s, tracked, aperture, blink_threshold):
    """Eyelid opening: left against right, and start of session against end.

    The second comparison is the reason this block exists. A droop that is present
    throughout is one thing; a droop that appears only after a minute of sustained
    effort is a different and specifically described phenomenon, and the subtest
    happens to be exactly the kind of sustained effort that brings it out.
    """
    out = {
        "insufficient_data": True,
        "frames_analyzed": 0,
        "left_aperture_median": None,
        "right_aperture_median": None,
        "aperture_asymmetry_ratio": None,
        "aperture_relative_decline": None,
        "aperture_trend_per_min": None,
        "fatigue_window_s": None,
        "metric_notes": (
            "Medians are taken over open-eye frames only, so blinks do not drag "
            "them down. The asymmetry ratio is the difference between the two eyes "
            "over their mean. The decline compares the first and last "
            f"{round(FATIGUE_WINDOW_SHARE * 100)}% of the session and is only "
            f"computed for sessions of at least {MIN_SESSION_S_FOR_FATIGUE:.0f} "
            "seconds, below which normal variation swamps any trend. Left and right "
            "follow the landmark groups in tracking/landmarks.py and have not been "
            "verified against the subject's anatomical sides."
        ),
    }

    left = _attr_series(tracked, "left_eye_aperture")
    right = _attr_series(tracked, "right_eye_aperture")
    open_eyes = ~(np.isfinite(aperture) & (aperture < blink_threshold))

    left_open = left[np.isfinite(left) & open_eyes]
    right_open = right[np.isfinite(right) & open_eyes]
    if left_open.size < 10 or right_open.size < 10:
        return out

    left_median = float(np.median(left_open))
    right_median = float(np.median(right_open))
    mean_aperture = (left_median + right_median) / 2.0

    out.update({
        "insufficient_data": False,
        "frames_analyzed": int(min(left_open.size, right_open.size)),
        "left_aperture_median": _round(left_median, 4),
        "right_aperture_median": _round(right_median, 4),
        "aperture_asymmetry_ratio": (
            _round(abs(left_median - right_median) / mean_aperture, 4)
            if mean_aperture > 1e-6 else None
        ),
    })

    span_s = float(times_s[-1] - times_s[0]) if times_s.size >= 2 else 0.0
    both = np.where(open_eyes & np.isfinite(left) & np.isfinite(right),
                    (left + right) / 2.0, np.nan)
    have = np.isfinite(both)
    if span_s >= MIN_SESSION_S_FOR_FATIGUE and int(np.count_nonzero(have)) >= 30:
        window = span_s * FATIGUE_WINDOW_SHARE
        early = have & (times_s <= times_s[0] + window)
        late = have & (times_s >= times_s[-1] - window)
        if np.any(early) and np.any(late):
            first = float(np.median(both[early]))
            last = float(np.median(both[late]))
            out["fatigue_window_s"] = _round(window, 2)
            if first > 1e-6:
                out["aperture_relative_decline"] = _round((first - last) / first, 4)
        slope = np.polyfit(times_s[have], both[have], 1)[0]
        out["aperture_trend_per_min"] = _round(slope * 60.0, 4)

    return out


def head_control(times_s, yaw, iris_h, moving_mask, sweeps, head_block, yaw_raw=None):
    """Direction-dependent behaviour of the head and of gaze stabilisation.

    THE MEASUREMENT WORTH THE MOST HERE
        Gaze stabilisation that is fine turning one way and poor turning the other
        is the classic pattern of a one-sided vestibular loss, and it is invisible
        to any whole-session average: a session with one good direction and one bad
        one averages out to the same residual as a session that was mediocre
        throughout. Splitting the residual by sweep direction is cheap and it is
        the single most informative thing this capture can be asked beyond the
        original subtest.
    """
    out = {
        "insufficient_data": True,
        "leftward_residual_rms_offset_units": None,
        "rightward_residual_rms_offset_units": None,
        "direction_asymmetry_index": None,
        "leftward_sweeps": 0,
        "rightward_sweeps": 0,
        "leftward_mean_peak_velocity_dps": None,
        "rightward_mean_peak_velocity_dps": None,
        "velocity_asymmetry_index": None,
        "tremor_frequency_hz": None,
        "tremor_rhythmicity": None,
        "tremor_amplitude_deg": None,
        "sample_rate_hz": None,
        "tremor_band_hz": list(TREMOR_BAND_HZ),
        "off_axis_coupling_ratio": None,
        "metric_notes": (
            "The asymmetry index is the difference between the two directions over "
            "their sum, so 0 means the two directions behaved identically and 1 "
            "means one direction carried everything. It needs at least two sweeps "
            "in each direction to mean anything. Tremor is measured on the yaw "
            "trace after removing motion slower than "
            f"{TREMOR_HIGHPASS_WINDOW_S} s, and like the eye oscillation search it "
            "is bounded by the capture frame rate rather than by physiology. "
            "Off-axis coupling is roll plus pitch range over yaw range: the "
            "subtest asks for pure rotation, so a high value means the head tilted "
            "or nodded instead of turning, though the pose decomposition also "
            "couples axes at large yaw and inflates it."
        ),
    }

    reconstructed = compensation_residual(yaw, iris_h, moving_mask)
    positive = [s for s in sweeps if s.get("direction") == "toward_positive_yaw"]
    negative = [s for s in sweeps if s.get("direction") == "toward_negative_yaw"]
    out["leftward_sweeps"] = len(positive)
    out["rightward_sweeps"] = len(negative)

    def in_windows(group):
        mask = np.zeros(times_s.shape, dtype=bool)
        for sweep in group:
            start, end = sweep.get("start_s"), sweep.get("end_s")
            if start is None or end is None:
                continue
            mask |= (times_s >= start) & (times_s <= end)
        return mask

    if positive and negative:
        for group, key in ((positive, "leftward"), (negative, "rightward")):
            peaks = [
                s["peak_angular_velocity_dps"] for s in group
                if isinstance(s.get("peak_angular_velocity_dps"), (int, float))
            ]
            if peaks:
                out[f"{key}_mean_peak_velocity_dps"] = _round(np.mean(peaks), 2)

        left_v = out["leftward_mean_peak_velocity_dps"]
        right_v = out["rightward_mean_peak_velocity_dps"]
        if left_v and right_v and left_v + right_v > 1e-9:
            out["velocity_asymmetry_index"] = _round(
                abs(left_v - right_v) / (left_v + right_v), 4
            )
        out["insufficient_data"] = False

    if reconstructed is not None and positive and negative:
        residual, valid = reconstructed
        rms = {}
        for group, key in ((positive, "leftward"), (negative, "rightward")):
            mask = in_windows(group) & valid & moving_mask
            if int(np.count_nonzero(mask)) >= 5:
                rms[key] = float(np.sqrt(np.mean(residual[mask] ** 2)))
                out[f"{key}_residual_rms_offset_units"] = _round(rms[key])
        if len(rms) == 2 and sum(rms.values()) > 1e-12:
            out["direction_asymmetry_index"] = _round(
                abs(rms["leftward"] - rms["rightward"]) / sum(rms.values()), 4
            )

    # ---- tremor, on the yaw trace itself rather than on gaze, and on the
    # UNSMOOTHED trace: the boxcar the session applies before sweep detection cuts
    # a 4 Hz oscillation to under half its real amplitude.
    trace = yaw_raw if yaw_raw is not None and yaw_raw.size == times_s.size else yaw
    if times_s.size >= 16:
        span_s = float(times_s[-1] - times_s[0])
        if span_s > 0:
            rate = (times_s.size - 1) / span_s
            window = max(3, int(round(TREMOR_HIGHPASS_WINDOW_S * rate)))
            fast = trace - metrics.moving_average(trace, window)
            found = metrics.dominant_frequency(fast, times_s, TREMOR_BAND_HZ)
            out["tremor_frequency_hz"] = found.frequency_hz
            out["tremor_rhythmicity"] = found.rhythmicity
            out["sample_rate_hz"] = found.sample_rate_hz
            if found.amplitude_rms is not None:
                # Peak to peak of the equivalent sinusoid, which is the form head
                # tremor amplitude is normally quoted in.
                out["tremor_amplitude_deg"] = _round(
                    found.amplitude_rms * 2.0 * np.sqrt(2.0), 3
                )

    yaw_range = head_block.get("yaw_range_deg")
    roll_range = head_block.get("roll_range_deg")
    pitch_range = head_block.get("pitch_range_deg")
    if (
        isinstance(yaw_range, (int, float)) and yaw_range > 1e-6
        and isinstance(roll_range, (int, float))
        and isinstance(pitch_range, (int, float))
    ):
        out["off_axis_coupling_ratio"] = _round(
            (roll_range + pitch_range) / yaw_range, 4
        )

    return out


def facial_symmetry(tracked):
    """Resting height difference between the two sides of the mouth and brows.

    Only frames captured near frontal contribute, because the tracker returns None
    for the rest (see tracking/face_tracker.MAX_YAW_FOR_SYMMETRY_DEG). In a subtest
    built entirely out of turning the head, that can leave very few usable frames,
    so the count is reported and the interpretation layer gates on it.
    """
    out = {
        "insufficient_data": True,
        "frames_analyzed": 0,
        "mouth_corner_asymmetry": None,
        "brow_height_asymmetry": None,
        "mouth_corner_asymmetry_spread": None,
        "metric_notes": (
            "Measured in face-width units inside a head-roll corrected face frame, "
            "over near-frontal frames only. Positive means the landmarks.py 'left' "
            "side sits higher. Those side labels have not been verified against the "
            "subject's anatomical sides, so read the magnitude as measured and "
            "confirm the affected side by looking at the person. A face at rest is "
            "never perfectly symmetric, and this measure cannot separate a "
            "long-standing natural difference from a new one."
        ),
    }

    mouth = _attr_series(tracked, "mouth_corner_asymmetry")
    brow = _attr_series(tracked, "brow_height_asymmetry")
    usable = np.isfinite(mouth)
    count = int(np.count_nonzero(usable))
    if count < 10:
        return out

    values = mouth[usable]
    out.update({
        "insufficient_data": False,
        "frames_analyzed": count,
        "mouth_corner_asymmetry": _round(np.median(values), 4),
        "mouth_corner_asymmetry_spread": _round(
            np.percentile(values, 75) - np.percentile(values, 25), 4
        ),
    })
    if np.any(np.isfinite(brow)):
        out["brow_height_asymmetry"] = _round(np.median(brow[np.isfinite(brow)]), 4)
    return out
