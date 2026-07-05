"""Event stream representations: fixed-time packets, count frames, time surfaces, edge images.

All helpers accept the project structured event array (``EVENT_DTYPE`` fields
``t``, ``x``, ``y``, ``p``). Polarity is interpreted as positive when ``p > 0``
so both ``{-1, +1}`` and ``{0, 1}`` source conventions are handled.
"""

from dataclasses import dataclass

import numpy as np

from nav_benchmark.datasets.mvsec import MvsecSequence


@dataclass(frozen=True)
class EventPacket:
    """Events falling in the half-open window ``[t_start, t_end)``.

    The final packet produced by :func:`packetize_events` is closed on the
    right so the last event of a stream is never dropped.
    """

    t_start: float
    t_end: float
    events: np.ndarray

    def __len__(self) -> int:
        return len(self.events)


def _require_positive_window(window_sec: float) -> None:
    if window_sec <= 0.0:
        raise ValueError("window_sec must be positive")


def _require_resolution(height: int, width: int) -> None:
    if height <= 0 or width <= 0:
        raise ValueError("height and width must be positive")


def _require_in_bounds(x: np.ndarray, y: np.ndarray, height: int, width: int) -> None:
    if len(x) == 0:
        return
    if int(x.max()) >= width or int(y.max()) >= height:
        raise ValueError(f"event coordinates exceed the {height}x{width} frame resolution")


def _packet_window_bounds(t: np.ndarray, t_start: float | None, t_end: float | None) -> tuple[float, float]:
    start = float(t[0]) if t_start is None else float(t_start)
    end = float(t[-1]) if t_end is None else float(t_end)
    if end < start:
        raise ValueError("t_end must not be earlier than t_start")
    return start, end


def packetize_events(
    events: np.ndarray,
    window_sec: float,
    *,
    t_start: float | None = None,
    t_end: float | None = None,
) -> list[EventPacket]:
    """Split an event stream into fixed-duration packets, keeping empty windows."""
    _require_positive_window(window_sec)
    t = np.asarray(events["t"], dtype=np.float64)
    if len(t) == 0 and (t_start is None or t_end is None):
        return []

    start, end = _packet_window_bounds(t, t_start, t_end)
    window_count = max(int(np.ceil((end - start) / window_sec)), 1)
    edges = start + np.arange(window_count + 1, dtype=np.float64) * window_sec
    indices = np.searchsorted(t, edges, side="left")
    # Close the final window on the right so an event at exactly `end` is kept.
    indices[-1] = int(np.searchsorted(t, edges[-1], side="right"))

    return [
        EventPacket(
            t_start=float(edges[k]),
            t_end=float(edges[k + 1]),
            events=events[indices[k] : indices[k + 1]],
        )
        for k in range(window_count)
    ]


def event_count_frame(events: np.ndarray, height: int, width: int) -> np.ndarray:
    """Per-pixel event counts as a ``(2, height, width)`` array: channel 0 positive, channel 1 negative."""
    _require_resolution(height, width)
    frame = np.zeros((2, height, width), dtype=np.int64)
    if len(events) == 0:
        return frame

    x = np.asarray(events["x"], dtype=np.int64)
    y = np.asarray(events["y"], dtype=np.int64)
    _require_in_bounds(x, y, height, width)

    positive = np.asarray(events["p"]) > 0
    np.add.at(frame[0], (y[positive], x[positive]), 1)
    np.add.at(frame[1], (y[~positive], x[~positive]), 1)
    return frame


def time_surface(
    events: np.ndarray,
    height: int,
    width: int,
    *,
    t_ref: float | None = None,
    tau_sec: float = 0.030,
) -> np.ndarray:
    """Exponentially decayed recency of the latest event per pixel.

    Pixels that never fired are 0. A pixel that fired exactly at ``t_ref`` is 1;
    older events decay as ``exp(-(t_ref - t_latest) / tau_sec)``.
    """
    _require_resolution(height, width)
    if tau_sec <= 0.0:
        raise ValueError("tau_sec must be positive")

    surface = np.zeros((height, width), dtype=np.float64)
    if len(events) == 0:
        return surface

    t = np.asarray(events["t"], dtype=np.float64)
    x = np.asarray(events["x"], dtype=np.int64)
    y = np.asarray(events["y"], dtype=np.int64)
    _require_in_bounds(x, y, height, width)

    reference = float(t[-1]) if t_ref is None else float(t_ref)
    latest = np.full((height, width), -np.inf, dtype=np.float64)
    np.maximum.at(latest, (y, x), t)

    fired = np.isfinite(latest)
    surface[fired] = np.exp(-(reference - latest[fired]) / tau_sec)
    return surface


def accumulate_event_edges(events: np.ndarray, height: int, width: int, *, normalize: bool = True) -> np.ndarray:
    """Accumulated event-edge image: per-pixel total count over both polarities.

    With ``normalize=True`` the image is scaled so the strongest pixel is 1.0.
    """
    counts = event_count_frame(events, height, width)
    edges = (counts[0] + counts[1]).astype(np.float64)
    if not normalize:
        return edges
    peak = float(edges.max()) if edges.size else 0.0
    if peak > 0.0:
        edges = edges / peak
    return edges


def event_frames_from_events(
    events: np.ndarray,
    height: int,
    width: int,
    *,
    window_sec: float = 0.050,
) -> tuple[np.ndarray, np.ndarray]:
    """Build uint8 event-edge frames plus window-center timestamps for frame-based VO."""
    packets = packetize_events(events, window_sec)
    frames = np.zeros((len(packets), height, width), dtype=np.uint8)
    timestamps = np.zeros(len(packets), dtype=np.float64)
    for i, packet in enumerate(packets):
        edges = accumulate_event_edges(packet.events, height, width)
        frames[i] = np.round(edges * 255.0).astype(np.uint8)
        timestamps[i] = 0.5 * (packet.t_start + packet.t_end)
    return frames, timestamps


def infer_sequence_resolution(sequence: MvsecSequence) -> tuple[int, int]:
    """Best-effort ``(height, width)`` from loaded images, falling back to event extents."""
    if sequence.images is not None and len(sequence.images) > 0:
        return int(sequence.images.shape[1]), int(sequence.images.shape[2])
    if sequence.events is not None and len(sequence.events) > 0:
        return int(sequence.events["y"].max()) + 1, int(sequence.events["x"].max()) + 1
    raise ValueError("Cannot infer sensor resolution: sequence has no images and no events")


def ensure_event_frames(sequence: MvsecSequence, *, window_sec: float = 0.050) -> bool:
    """Build ``event_frames`` from raw events when a sequence has none.

    Returns True when frames were built, False when the sequence already has
    frames or carries no events to build them from.
    """
    if sequence.event_frames is not None:
        return False
    if sequence.events is None or len(sequence.events) == 0:
        return False

    height, width = infer_sequence_resolution(sequence)
    frames, timestamps = event_frames_from_events(sequence.events, height, width, window_sec=window_sec)
    if len(frames) == 0:
        return False

    sequence.event_frames = frames
    sequence.event_frame_timestamps = timestamps
    sequence.metadata.sample_counts["event_frames"] = len(frames)
    sequence.metadata.time_ranges["event_frames"] = (float(timestamps[0]), float(timestamps[-1]))
    return True
