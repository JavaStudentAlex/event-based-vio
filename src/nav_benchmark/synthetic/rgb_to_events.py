"""Convert recorded RGB frames into a synthetic event-camera stream (Phase 5).

A simple, controllable log-intensity threshold model: for each consecutive frame pair, compute
``delta = log(I_curr + eps) - log(I_prev + eps)`` on normalized grayscale, emit ``+1`` where
``delta >= positive_threshold`` and ``-1`` where ``delta <= -negative_threshold``. Event
timestamps are the midpoint between the two frame timestamps. Good for tests/control; can later
be compared against v2e/ESIM without changing the downstream contract.
"""

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nav_benchmark.datasets.mvsec import EVENT_DTYPE
from nav_benchmark.synthetic.config import EventCameraCfg
from nav_benchmark.synthetic.imageio import load_png_gray

EVENTS_CSV_HEADER = ["timestamp_s", "x", "y", "polarity"]
EVENT_TIMESTAMPS_HEADER = ["frame_pair", "t_prev_s", "t_curr_s", "t_event_s", "num_events"]
_LOG_EPS = 1e-3


@dataclass
class EventArrays:
    t: np.ndarray  # (N,) float64 seconds
    x: np.ndarray  # (N,) int
    y: np.ndarray  # (N,) int
    p: np.ndarray  # (N,) int8 in {-1, +1}
    width: int
    height: int

    def __len__(self) -> int:
        return int(self.t.size)


def pair_to_events(
    prev_gray: np.ndarray, curr_gray: np.ndarray, cfg: EventCameraCfg
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(xs, ys, ps)`` for one frame pair via the log-intensity threshold model."""
    prev = np.asarray(prev_gray, dtype=np.float64) / 255.0
    curr = np.asarray(curr_gray, dtype=np.float64) / 255.0
    delta = np.log(curr + _LOG_EPS) - np.log(prev + _LOG_EPS)

    pos = delta >= cfg.positive_threshold
    neg = delta <= -cfg.negative_threshold

    ys_pos, xs_pos = np.nonzero(pos)
    ys_neg, xs_neg = np.nonzero(neg)

    xs = np.concatenate([xs_pos, xs_neg])
    ys = np.concatenate([ys_pos, ys_neg])
    ps = np.concatenate([np.ones(xs_pos.size, dtype=np.int8), -np.ones(xs_neg.size, dtype=np.int8)])

    if xs.size > cfg.max_events_per_frame_pair:
        # Deterministically keep the strongest threshold crossings.
        mags = np.abs(np.concatenate([delta[ys_pos, xs_pos], delta[ys_neg, xs_neg]]))
        keep = np.argsort(mags)[::-1][: cfg.max_events_per_frame_pair]
        keep.sort()
        xs, ys, ps = xs[keep], ys[keep], ps[keep]
    return xs, ys, ps


def frames_to_events(
    frame_grays: Iterator[np.ndarray] | list[np.ndarray],
    timestamps: np.ndarray,
    cfg: EventCameraCfg,
    width: int,
    height: int,
) -> tuple[EventArrays, list[tuple[int, float, float, float, int]]]:
    """Convert an iterable of grayscale frames into events. Returns (events, per-pair stats)."""
    timestamps = np.asarray(timestamps, dtype=np.float64)
    iterator = iter(frame_grays)
    try:
        prev = next(iterator)
    except StopIteration as exc:
        raise ValueError("Need at least 2 frames to generate events") from exc

    t_list: list[np.ndarray] = []
    x_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    p_list: list[np.ndarray] = []
    pair_stats: list[tuple[int, float, float, float, int]] = []

    for i, curr in enumerate(iterator, start=1):
        t_prev, t_curr = float(timestamps[i - 1]), float(timestamps[i])
        t_event = 0.5 * (t_prev + t_curr)
        xs, ys, ps = pair_to_events(prev, curr, cfg)
        if xs.size:
            t_list.append(np.full(xs.size, t_event, dtype=np.float64))
            x_list.append(xs.astype(np.int32))
            y_list.append(ys.astype(np.int32))
            p_list.append(ps)
        pair_stats.append((i - 1, t_prev, t_curr, t_event, int(xs.size)))
        prev = curr

    if t_list:
        events = EventArrays(
            t=np.concatenate(t_list),
            x=np.concatenate(x_list),
            y=np.concatenate(y_list),
            p=np.concatenate(p_list),
            width=width,
            height=height,
        )
    else:
        events = EventArrays(
            t=np.empty(0, dtype=np.float64),
            x=np.empty(0, dtype=np.int32),
            y=np.empty(0, dtype=np.int32),
            p=np.empty(0, dtype=np.int8),
            width=width,
            height=height,
        )
    return events, pair_stats


def write_events_csv(events: EventArrays, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(EVENTS_CSV_HEADER)
        for i in range(len(events)):
            writer.writerow([f"{events.t[i]:.6f}", int(events.x[i]), int(events.y[i]), int(events.p[i])])


def write_events_h5(events: EventArrays, path: str | Path) -> None:
    import h5py  # type: ignore

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    structured = np.empty(len(events), dtype=EVENT_DTYPE)
    structured["t"] = events.t
    structured["x"] = events.x
    structured["y"] = events.y
    structured["p"] = events.p
    with h5py.File(path, "w") as f:
        dset = f.create_dataset("events", data=structured, compression="gzip")
        dset.attrs["width"] = events.width
        dset.attrs["height"] = events.height
        dset.attrs["model"] = "log_intensity_threshold"


def write_event_timestamps_csv(pair_stats: list[tuple[int, float, float, float, int]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(EVENT_TIMESTAMPS_HEADER)
        for frame_pair, t_prev, t_curr, t_event, num in pair_stats:
            writer.writerow([frame_pair, f"{t_prev:.6f}", f"{t_curr:.6f}", f"{t_event:.6f}", num])


def _iter_frame_grays(rgb_dir: Path, rel_paths: list[str]) -> Iterator[np.ndarray]:
    for rel in rel_paths:
        yield load_png_gray(rgb_dir / Path(rel).name)


def convert_sequence(
    output_dir: str | Path,
    cfg: EventCameraCfg,
    width: int,
    height: int,
) -> EventArrays:
    """Read ``rgb/`` + ``metadata/rgb_timestamps.csv`` and write events.csv/.h5 + event_timestamps.csv."""
    output_dir = Path(output_dir)
    rgb_dir = output_dir / "rgb"
    ts_csv = output_dir / "metadata" / "rgb_timestamps.csv"
    if not ts_csv.exists():
        raise FileNotFoundError(f"rgb_timestamps.csv not found: {ts_csv}")

    rel_paths: list[str] = []
    timestamps: list[float] = []
    with open(ts_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel_paths.append(row["path"])
            timestamps.append(float(row["timestamp_s"]))

    frames = [load_png_gray(rgb_dir / Path(rel).name) for rel in rel_paths]
    events, pair_stats = frames_to_events(frames, np.asarray(timestamps), cfg, width, height)

    if cfg.output_csv:
        write_events_csv(events, output_dir / "events" / "events.csv")
    if cfg.output_h5:
        write_events_h5(events, output_dir / "events" / "events.h5")
    write_event_timestamps_csv(pair_stats, output_dir / "metadata" / "event_timestamps.csv")
    return events
