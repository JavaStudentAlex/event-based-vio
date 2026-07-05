import numpy as np
import pytest

from nav_benchmark.datasets.mvsec import EVENT_DTYPE
from nav_benchmark.events import diagnose_event_stream


def _events(rows: list[tuple[float, int, int, int]]) -> np.ndarray:
    events = np.empty(len(rows), dtype=EVENT_DTYPE)
    for i, (t, x, y, p) in enumerate(rows):
        events[i] = (t, x, y, p)
    return events


def test_empty_stream_reports_zeroed_diagnostics():
    diag = diagnose_event_stream(_events([]), height=4, width=4, window_sec=0.02)

    assert diag.total_events == 0
    assert diag.duration_sec == 0.0
    assert diag.mean_event_rate_hz == 0.0
    assert diag.positive_fraction == 0.0
    assert diag.active_pixel_fraction == 0.0
    assert diag.hot_pixel_fraction == 0.0
    assert diag.window_sec == 0.02
    assert diag.window_count == 0
    assert diag.starved is False
    assert diag.overloaded is False


def test_basic_rates_polarity_and_activity():
    # 4 events over 0.2 s on a 2x2 sensor, 3 positive and 1 negative, 2 distinct pixels.
    events = _events(
        [
            (0.0, 0, 0, 1),
            (0.1, 0, 0, 1),
            (0.15, 1, 1, -1),
            (0.2, 0, 0, 1),
        ]
    )
    diag = diagnose_event_stream(events, height=2, width=2, window_sec=0.1, min_rate_hz=0.0, max_rate_hz=1e9)

    assert diag.total_events == 4
    assert diag.duration_sec == pytest.approx(0.2)
    assert diag.mean_event_rate_hz == pytest.approx(20.0)
    assert diag.positive_fraction == pytest.approx(0.75)
    assert diag.active_pixel_fraction == pytest.approx(0.5)
    assert diag.window_count == 2
    assert diag.starved_window_count == 0
    assert diag.overloaded_window_count == 0
    # Window 1 has one event (t=0.0..0.1 exclusive), window 2 has three (0.1, 0.15, 0.2).
    assert diag.min_window_rate_hz == pytest.approx(10.0)
    assert diag.max_window_rate_hz == pytest.approx(30.0)


def test_starved_windows_are_counted():
    # Window rate: 2 events / 0.1 s = 20 Hz in the first window, 1 event / 0.1 s = 10 Hz in the last.
    events = _events(
        [
            (0.00, 0, 0, 1),
            (0.05, 0, 0, 1),
            (0.20, 1, 1, 1),
        ]
    )
    diag = diagnose_event_stream(events, height=2, width=2, window_sec=0.1, min_rate_hz=15.0, max_rate_hz=1e9)

    assert diag.window_count == 2
    assert diag.starved_window_count == 1
    assert diag.starved is True
    assert diag.overloaded is False


def test_overloaded_windows_are_counted():
    events = _events([(0.00, 0, 0, 1), (0.01, 0, 1, 1), (0.02, 1, 0, 1), (0.12, 1, 1, 1)])
    diag = diagnose_event_stream(events, height=2, width=2, window_sec=0.1, min_rate_hz=0.0, max_rate_hz=25.0)

    # First window rate is 30 Hz (3 events / 0.1 s), second is 10 Hz.
    assert diag.window_count == 2
    assert diag.overloaded_window_count == 1
    assert diag.overloaded is True
    assert diag.starved_window_count == 0


def test_hot_pixel_detection_uses_mean_of_fired_pixels():
    # Pixel (0,0) fires 40 times; three other pixels fire once each.
    rows = [(0.001 * i, 0, 0, 1) for i in range(40)]
    rows += [(0.05, 1, 0, 1), (0.06, 0, 1, 1), (0.07, 1, 1, 1)]
    events = _events(rows)

    # Mean over fired pixels = 43 / 4 = 10.75; hot threshold at 3x mean = 32.25 -> only (0,0) is hot.
    diag = diagnose_event_stream(events, height=2, width=2, window_sec=0.1, hot_pixel_factor=3.0)

    assert diag.active_pixel_fraction == pytest.approx(1.0)
    assert diag.hot_pixel_fraction == pytest.approx(0.25)


def test_uniform_pixels_have_no_hot_pixels():
    events = _events([(0.0, 0, 0, 1), (0.01, 1, 0, 1), (0.02, 0, 1, 1), (0.03, 1, 1, 1)])
    diag = diagnose_event_stream(events, height=2, width=2, window_sec=0.1, hot_pixel_factor=3.0)
    assert diag.hot_pixel_fraction == 0.0


def test_zero_and_negative_polarity_both_count_as_negative():
    events = _events([(0.0, 0, 0, 0), (0.01, 0, 0, -1), (0.02, 0, 0, 1), (0.03, 0, 0, 1)])
    diag = diagnose_event_stream(events, height=1, width=1, window_sec=0.1)
    assert diag.positive_fraction == pytest.approx(0.5)


def test_single_event_stream_has_zero_duration_and_rate():
    diag = diagnose_event_stream(_events([(1.0, 0, 0, 1)]), height=1, width=1, window_sec=0.05)
    assert diag.total_events == 1
    assert diag.duration_sec == 0.0
    assert diag.mean_event_rate_hz == 0.0
    assert diag.window_count == 1
