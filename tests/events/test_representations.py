import math

import numpy as np
import pytest

from nav_benchmark.datasets.mvsec import (
    EVENT_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
)
from nav_benchmark.events import (
    accumulate_event_edges,
    ensure_event_frames,
    event_count_frame,
    event_frames_from_events,
    infer_sequence_resolution,
    packetize_events,
    time_surface,
)


def _events(rows: list[tuple[float, int, int, int]]) -> np.ndarray:
    events = np.empty(len(rows), dtype=EVENT_DTYPE)
    for i, (t, x, y, p) in enumerate(rows):
        events[i] = (t, x, y, p)
    return events


def _sequence(**kwargs) -> MvsecSequence:
    return MvsecSequence(
        metadata=SequenceMetadata(source_path="test", sequence_name="test"),
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(),
        **kwargs,
    )


class TestPacketizeEvents:
    def test_windows_are_half_open_with_inclusive_final_edge(self):
        events = _events(
            [
                (0.00, 0, 0, 1),
                (0.01, 1, 0, 1),
                (0.02, 2, 0, -1),
                (0.049, 3, 0, 1),
                (0.05, 4, 0, -1),
                (0.10, 5, 0, 1),
            ]
        )
        packets = packetize_events(events, 0.05)

        assert len(packets) == 2
        assert packets[0].t_start == 0.0
        assert packets[0].t_end == 0.05
        assert len(packets[0]) == 4
        assert packets[1].t_start == 0.05
        assert packets[1].t_end == pytest.approx(0.10)
        assert len(packets[1]) == 2
        assert float(packets[1].events["t"][0]) == 0.05
        assert float(packets[1].events["t"][-1]) == 0.10

    def test_empty_windows_are_preserved(self):
        events = _events([(0.0, 0, 0, 1), (0.21, 0, 0, 1)])
        packets = packetize_events(events, 0.1)

        assert len(packets) == 3
        assert [len(p) for p in packets] == [1, 0, 1]

    def test_explicit_range_on_empty_stream(self):
        packets = packetize_events(_events([]), 0.05, t_start=0.0, t_end=0.2)
        assert len(packets) == 4
        assert all(len(p) == 0 for p in packets)

    def test_empty_stream_without_range_gives_no_packets(self):
        assert packetize_events(_events([]), 0.05) == []

    def test_single_event_stream_gives_single_packet(self):
        packets = packetize_events(_events([(1.0, 0, 0, 1)]), 0.05)
        assert len(packets) == 1
        assert len(packets[0]) == 1
        assert packets[0].t_start == 1.0

    def test_rejects_nonpositive_window(self):
        with pytest.raises(ValueError, match="window_sec"):
            packetize_events(_events([(0.0, 0, 0, 1)]), 0.0)

    def test_rejects_reversed_range(self):
        with pytest.raises(ValueError, match="t_end"):
            packetize_events(_events([(0.0, 0, 0, 1)]), 0.05, t_start=1.0, t_end=0.5)


class TestEventCountFrame:
    def test_polarity_channels_and_counts(self):
        events = _events([(0.0, 1, 0, 1), (0.1, 1, 0, 1), (0.2, 0, 1, -1)])
        frame = event_count_frame(events, height=2, width=3)

        assert frame.shape == (2, 2, 3)
        assert frame[0, 0, 1] == 2
        assert frame[1, 1, 0] == 1
        assert int(frame.sum()) == 3

    def test_zero_polarity_counts_as_negative(self):
        frame = event_count_frame(_events([(0.0, 0, 0, 0)]), height=1, width=1)
        assert frame[0, 0, 0] == 0
        assert frame[1, 0, 0] == 1

    def test_empty_events_give_zero_frame(self):
        frame = event_count_frame(_events([]), height=2, width=2)
        assert frame.shape == (2, 2, 2)
        assert int(frame.sum()) == 0

    def test_out_of_bounds_coordinates_raise(self):
        with pytest.raises(ValueError, match="exceed"):
            event_count_frame(_events([(0.0, 3, 0, 1)]), height=2, width=3)

    def test_invalid_resolution_raises(self):
        with pytest.raises(ValueError, match="positive"):
            event_count_frame(_events([]), height=0, width=3)


class TestTimeSurface:
    def test_exponential_decay_against_reference(self):
        events = _events([(0.0, 0, 0, 1), (0.1, 1, 1, -1)])
        surface = time_surface(events, height=2, width=2, t_ref=0.1, tau_sec=0.1)

        assert surface[0, 0] == pytest.approx(math.exp(-1.0))
        assert surface[1, 1] == pytest.approx(1.0)
        assert surface[0, 1] == 0.0
        assert surface[1, 0] == 0.0

    def test_latest_event_per_pixel_wins(self):
        events = _events([(0.02, 0, 0, 1), (0.08, 0, 0, 1)])
        surface = time_surface(events, height=1, width=1, t_ref=0.1, tau_sec=0.1)
        assert surface[0, 0] == pytest.approx(math.exp(-0.2))

    def test_default_reference_is_last_event(self):
        events = _events([(0.0, 0, 0, 1), (0.05, 1, 0, 1)])
        surface = time_surface(events, height=1, width=2, tau_sec=0.05)
        assert surface[0, 1] == pytest.approx(1.0)
        assert surface[0, 0] == pytest.approx(math.exp(-1.0))

    def test_empty_events_give_zero_surface(self):
        surface = time_surface(_events([]), height=2, width=2)
        assert float(surface.sum()) == 0.0

    def test_rejects_nonpositive_tau(self):
        with pytest.raises(ValueError, match="tau_sec"):
            time_surface(_events([(0.0, 0, 0, 1)]), height=1, width=1, tau_sec=0.0)


class TestAccumulateEventEdges:
    def test_counts_both_polarities_and_normalizes_to_peak(self):
        events = _events([(0.0, 0, 0, 1), (0.1, 0, 0, -1), (0.2, 1, 0, 1)])
        edges = accumulate_event_edges(events, height=1, width=2)

        assert edges[0, 0] == pytest.approx(1.0)
        assert edges[0, 1] == pytest.approx(0.5)

    def test_unnormalized_returns_raw_counts(self):
        events = _events([(0.0, 0, 0, 1), (0.1, 0, 0, -1)])
        edges = accumulate_event_edges(events, height=1, width=1, normalize=False)
        assert edges[0, 0] == 2.0

    def test_empty_events_stay_zero(self):
        edges = accumulate_event_edges(_events([]), height=2, width=2)
        assert float(edges.max()) == 0.0


class TestEventFramesFromEvents:
    def test_frames_shapes_timestamps_and_peak_value(self):
        events = _events(
            [
                (0.00, 0, 0, 1),
                (0.01, 0, 0, -1),
                (0.02, 1, 1, 1),
                (0.06, 1, 0, 1),
            ]
        )
        frames, timestamps = event_frames_from_events(events, height=2, width=2, window_sec=0.05)

        assert frames.shape == (2, 2, 2)
        assert frames.dtype == np.uint8
        assert timestamps.tolist() == pytest.approx([0.025, 0.075])
        assert frames[0, 0, 0] == 255
        assert frames[0, 1, 1] == 128
        assert frames[1, 0, 1] == 255

    def test_empty_stream_yields_no_frames(self):
        frames, timestamps = event_frames_from_events(_events([]), height=2, width=2)
        assert frames.shape == (0, 2, 2)
        assert len(timestamps) == 0


class TestSequenceHelpers:
    def test_resolution_from_images_takes_priority(self):
        sequence = _sequence(
            images=np.zeros((2, 4, 6), dtype=np.uint8),
            events=_events([(0.0, 9, 9, 1)]),
        )
        assert infer_sequence_resolution(sequence) == (4, 6)

    def test_resolution_from_event_extents(self):
        sequence = _sequence(events=_events([(0.0, 5, 3, 1), (0.1, 2, 7, -1)]))
        assert infer_sequence_resolution(sequence) == (8, 6)

    def test_resolution_requires_images_or_events(self):
        with pytest.raises(ValueError, match="resolution"):
            infer_sequence_resolution(_sequence())

    def test_ensure_event_frames_builds_from_raw_events(self):
        events = _events([(0.00, 0, 0, 1), (0.01, 1, 1, -1), (0.06, 1, 0, 1)])
        sequence = _sequence(events=events)

        assert ensure_event_frames(sequence, window_sec=0.05) is True
        assert sequence.event_frames is not None
        assert sequence.event_frames.shape == (2, 2, 2)
        assert sequence.event_frame_timestamps is not None
        assert sequence.metadata.sample_counts["event_frames"] == 2
        assert sequence.metadata.time_ranges["event_frames"] == pytest.approx((0.025, 0.075))

    def test_ensure_event_frames_keeps_existing_frames(self):
        existing = np.ones((1, 2, 2), dtype=np.uint8)
        sequence = _sequence(events=_events([(0.0, 0, 0, 1)]), event_frames=existing)

        assert ensure_event_frames(sequence) is False
        assert sequence.event_frames is existing

    def test_ensure_event_frames_without_events_is_noop(self):
        sequence = _sequence()
        assert ensure_event_frames(sequence) is False
        assert sequence.event_frames is None
