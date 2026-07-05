"""Image-like 2D shift estimation between consecutive event frames.

This is the minimal event-derived motion cue for the ``event_imu`` backend:
a deterministic phase correlation between two accumulated event-edge frames.
It uses numpy FFTs only, so results are reproducible across runs and do not
depend on optional OpenCV availability.

Conventions:
- ``shift_px`` is the displacement of frame *content* from the previous frame
  to the current frame, as ``(dx, dy)`` in pixels. If the current frame equals
  ``np.roll(prev, (dy, dx), axis=(0, 1))``, the estimate is ``(dx, dy)``.
- ``confidence`` is a deterministic 0..1 score built from the distinctness of
  the correlation peak and the event activity of both frames. It is a heuristic
  quality score, not a calibrated probability.
"""

from dataclasses import dataclass

import numpy as np

_MIN_SHIFT_FRAME_SIDE = 4
# Active-pixel fraction at which the activity score saturates at 1.0.
_FULL_ACTIVITY_FRACTION = 0.01
# Neighborhood half-width excluded around the main peak when searching for the
# second-highest correlation peak.
_PEAK_EXCLUSION_RADIUS = 2


@dataclass(frozen=True)
class ShiftEstimate:
    """Result of one event-frame pair shift estimation."""

    dx_px: float
    dy_px: float
    confidence: float
    valid: bool
    reason: str

    @property
    def shift_px(self) -> np.ndarray:
        return np.array([self.dx_px, self.dy_px], dtype=np.float64)


def _invalid_estimate(reason: str) -> ShiftEstimate:
    return ShiftEstimate(dx_px=0.0, dy_px=0.0, confidence=0.0, valid=False, reason=reason)


def _as_float_gray(frame: np.ndarray) -> np.ndarray:
    arr = np.asarray(frame, dtype=np.float64)
    if arr.ndim == 3:
        arr = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    if arr.ndim != 2:
        raise ValueError("shift estimation expects 2D (or RGB) frames")
    return arr


def _frame_reason(gray: np.ndarray) -> str | None:
    """Reason this frame cannot be correlated, or None when it is usable."""
    if min(gray.shape) < _MIN_SHIFT_FRAME_SIDE:
        return "frame_too_small"
    if not np.all(np.isfinite(gray)):
        return "non_finite_frame"
    if np.count_nonzero(gray) == 0:
        return "empty_frame"
    return None


def _active_fraction(gray: np.ndarray) -> float:
    return float(np.count_nonzero(gray) / max(gray.size, 1))


def _hann_window_2d(height: int, width: int) -> np.ndarray:
    return np.outer(np.hanning(height), np.hanning(width))


def _wrap_offset(index: int, size: int) -> float:
    return float(index - size) if index > size // 2 else float(index)


def _parabolic_refine(response: np.ndarray, peak_index: int, axis_size: int) -> float:
    """Sub-pixel peak refinement along one axis using the wrapped neighbors."""
    left = float(response[(peak_index - 1) % axis_size])
    center = float(response[peak_index])
    right = float(response[(peak_index + 1) % axis_size])
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return 0.0
    offset = 0.5 * (left - right) / denominator
    return float(np.clip(offset, -0.5, 0.5))


def _second_peak(response: np.ndarray, peak_y: int, peak_x: int) -> float:
    masked = response.copy()
    height, width = response.shape
    ys = (np.arange(-_PEAK_EXCLUSION_RADIUS, _PEAK_EXCLUSION_RADIUS + 1) + peak_y) % height
    xs = (np.arange(-_PEAK_EXCLUSION_RADIUS, _PEAK_EXCLUSION_RADIUS + 1) + peak_x) % width
    masked[np.ix_(ys, xs)] = -np.inf
    return float(masked.max())


def _peak_confidence(response: np.ndarray, peak_y: int, peak_x: int, activity_score: float) -> float:
    peak = float(response[peak_y, peak_x])
    if peak <= 0.0:
        return 0.0
    second = max(_second_peak(response, peak_y, peak_x), 0.0)
    distinctness = (peak - second) / peak
    return float(np.clip(distinctness * activity_score, 0.0, 1.0))


def estimate_frame_shift(prev_frame: np.ndarray, curr_frame: np.ndarray) -> ShiftEstimate:
    """Estimate the 2D content shift between two event frames via phase correlation.

    Returns an invalid estimate (confidence 0) instead of raising for the
    expected failure modes: empty frames, non-finite data, or frames too small
    to correlate. A shape mismatch is a programming error and raises.
    """
    prev_gray = _as_float_gray(prev_frame)
    curr_gray = _as_float_gray(curr_frame)
    for gray in (prev_gray, curr_gray):
        reason = _frame_reason(gray)
        if reason is not None:
            return _invalid_estimate(reason)
    if prev_gray.shape != curr_gray.shape:
        raise ValueError(f"frame shapes differ: {prev_gray.shape} vs {curr_gray.shape}")

    height, width = prev_gray.shape
    prev_activity = _active_fraction(prev_gray)
    curr_activity = _active_fraction(curr_gray)

    window = _hann_window_2d(height, width)
    a = (prev_gray - prev_gray.mean()) * window
    b = (curr_gray - curr_gray.mean()) * window

    spectrum = np.conj(np.fft.fft2(a)) * np.fft.fft2(b)
    magnitude = np.abs(spectrum)
    magnitude[magnitude < 1e-12] = 1e-12
    response = np.real(np.fft.ifft2(spectrum / magnitude))

    peak_y, peak_x = np.unravel_index(int(np.argmax(response)), response.shape)
    dx = _wrap_offset(int(peak_x), width) + _parabolic_refine(response[peak_y, :], int(peak_x), width)
    dy = _wrap_offset(int(peak_y), height) + _parabolic_refine(response[:, peak_x], int(peak_y), height)

    activity_score = float(np.clip(min(prev_activity, curr_activity) / _FULL_ACTIVITY_FRACTION, 0.0, 1.0))
    confidence = _peak_confidence(response, int(peak_y), int(peak_x), activity_score)
    return ShiftEstimate(dx_px=float(dx), dy_px=float(dy), confidence=confidence, valid=True, reason="ok")
