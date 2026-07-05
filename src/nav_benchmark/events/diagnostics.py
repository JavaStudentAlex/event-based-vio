"""Event stream health diagnostics: rates, polarity balance, pixel activity, starvation/overload."""

from dataclasses import dataclass

import numpy as np

from nav_benchmark.events.representations import event_count_frame, packetize_events


@dataclass(frozen=True)
class EventStreamDiagnostics:
    """Summary health metrics for one event stream."""

    total_events: int
    duration_sec: float
    mean_event_rate_hz: float
    positive_fraction: float
    active_pixel_fraction: float
    hot_pixel_fraction: float
    window_sec: float
    window_count: int
    starved_window_count: int
    overloaded_window_count: int
    min_window_rate_hz: float
    max_window_rate_hz: float

    @property
    def starved(self) -> bool:
        return self.starved_window_count > 0

    @property
    def overloaded(self) -> bool:
        return self.overloaded_window_count > 0


def _empty_diagnostics(window_sec: float) -> EventStreamDiagnostics:
    return EventStreamDiagnostics(
        total_events=0,
        duration_sec=0.0,
        mean_event_rate_hz=0.0,
        positive_fraction=0.0,
        active_pixel_fraction=0.0,
        hot_pixel_fraction=0.0,
        window_sec=window_sec,
        window_count=0,
        starved_window_count=0,
        overloaded_window_count=0,
        min_window_rate_hz=0.0,
        max_window_rate_hz=0.0,
    )


def _window_rates(events: np.ndarray, window_sec: float) -> np.ndarray:
    packets = packetize_events(events, window_sec)
    return np.array([len(packet) / window_sec for packet in packets], dtype=np.float64)


def _pixel_activity(events: np.ndarray, height: int, width: int, hot_pixel_factor: float) -> tuple[float, float]:
    counts = event_count_frame(events, height, width)
    per_pixel = (counts[0] + counts[1]).astype(np.float64)
    fired = per_pixel > 0
    fired_count = int(np.count_nonzero(fired))
    if fired_count == 0:
        return 0.0, 0.0

    pixel_count = float(height * width)
    mean_fired = float(per_pixel[fired].mean())
    hot = per_pixel > hot_pixel_factor * mean_fired
    return fired_count / pixel_count, float(np.count_nonzero(hot)) / pixel_count


def diagnose_event_stream(
    events: np.ndarray,
    height: int,
    width: int,
    *,
    window_sec: float = 0.050,
    min_rate_hz: float = 1_000.0,
    max_rate_hz: float = 5_000_000.0,
    hot_pixel_factor: float = 10.0,
) -> EventStreamDiagnostics:
    """Compute stream-level event health metrics over fixed-duration windows.

    A window is starved when its event rate falls below ``min_rate_hz`` and
    overloaded when it exceeds ``max_rate_hz``.
    """
    if events is None or len(events) == 0:
        return _empty_diagnostics(window_sec)

    t = np.asarray(events["t"], dtype=np.float64)
    duration = float(t[-1] - t[0])
    total = len(events)
    mean_rate = total / duration if duration > 0.0 else 0.0
    positive_fraction = float(np.count_nonzero(np.asarray(events["p"]) > 0)) / total

    rates = _window_rates(events, window_sec)
    active_fraction, hot_fraction = _pixel_activity(events, height, width, hot_pixel_factor)

    return EventStreamDiagnostics(
        total_events=total,
        duration_sec=duration,
        mean_event_rate_hz=mean_rate,
        positive_fraction=positive_fraction,
        active_pixel_fraction=active_fraction,
        hot_pixel_fraction=hot_fraction,
        window_sec=window_sec,
        window_count=len(rates),
        starved_window_count=int(np.count_nonzero(rates < min_rate_hz)),
        overloaded_window_count=int(np.count_nonzero(rates > max_rate_hz)),
        min_window_rate_hz=float(rates.min()),
        max_window_rate_hz=float(rates.max()),
    )
