"""Record raw RGB frames and synchronized drone state (Phase 1 + 2).

Timestamps come from a monotonic clock (never wall-clock). The recorder saves the **raw**
captured frame only — telemetry overlays belong in previews, not in ``rgb/`` (an overlay would
become fake image content and corrupt event conversion / odometry). The loop is split from the
clock so it can be unit-tested with fakes and a simulated clock (no real-time sleeping).
"""

import csv
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from nav_benchmark.synthetic.config import SequenceConfig
from nav_benchmark.synthetic.imageio import save_png_rgb

RGB_TIMESTAMPS_HEADER = ["frame_id", "timestamp_s", "path"]
RAW_STATE_HEADER = ["timestamp_s", "lat", "lon", "alt_m", "heading_deg", "speed_mps"]


class Clock(Protocol):
    def start(self) -> None: ...
    def now(self) -> float: ...
    def wait_until(self, t_s: float) -> None: ...


class RealtimeClock:
    """Monotonic real-time clock that sleeps to pace capture at the target FPS."""

    def __init__(self) -> None:
        self._t0_ns = 0

    def start(self) -> None:
        self._t0_ns = time.monotonic_ns()

    def now(self) -> float:
        return (time.monotonic_ns() - self._t0_ns) * 1e-9

    def wait_until(self, t_s: float) -> None:
        remaining = t_s - self.now()
        if remaining > 0:
            time.sleep(remaining)


class SimulatedClock:
    """Deterministic clock: advances to the requested time without sleeping (tests/synthetic)."""

    def __init__(self) -> None:
        self._t = 0.0

    def start(self) -> None:
        self._t = 0.0

    def now(self) -> float:
        return self._t

    def wait_until(self, t_s: float) -> None:
        self._t = t_s


@dataclass
class RecordResult:
    output_dir: Path
    frame_paths: list[str]
    timestamps: np.ndarray
    states: list[dict[str, float]]
    width: int
    height: int
    missing_frames: list[int] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        return len(self.frame_paths)

    @property
    def duration_s(self) -> float:
        return float(self.timestamps[-1]) if self.timestamps.size else 0.0


def _frame_rel_path(frame_id: int) -> str:
    return f"rgb/frame_{frame_id:06d}.png"


def write_rgb_timestamps_csv(result: RecordResult, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(RGB_TIMESTAMPS_HEADER)
        for i, rel in enumerate(result.frame_paths):
            writer.writerow([i, f"{result.timestamps[i]:.6f}", rel])


def write_raw_state_log_csv(result: RecordResult, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(RAW_STATE_HEADER)
        for i, s in enumerate(result.states):
            writer.writerow(
                [
                    f"{result.timestamps[i]:.6f}",
                    f"{s['lat']:.8f}",
                    f"{s['lon']:.8f}",
                    f"{s['alt']:.3f}",
                    f"{s['heading']:.4f}",
                    f"{s['speed']:.4f}",
                ]
            )


def record(
    config: SequenceConfig,
    frame_source,
    drone,
    output_dir: str | Path,
    *,
    clock: Clock | None = None,
    log: Callable[[str], None] = print,
) -> RecordResult:
    """Record ``duration_s`` of raw RGB frames + drone state into ``output_dir``.

    ``frame_source`` and ``drone`` are duck-typed (see :mod:`frame_source` / :mod:`drone_model`),
    which keeps this loop unit-testable with fakes.
    """
    output_dir = Path(output_dir)
    rgb_dir = output_dir / "rgb"
    meta_dir = output_dir / "metadata"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    fps = config.recording.capture_fps
    duration_s = config.sequence.duration_s
    n_frames = max(round(duration_s * fps), 1)
    width, height = config.camera.width, config.camera.height

    clock = clock or RealtimeClock()
    frame_paths: list[str] = []
    timestamps: list[float] = []
    states: list[dict[str, float]] = []
    missing: list[int] = []

    frame_source.start()
    clock.start()
    last_t = -1.0
    try:
        for i in range(n_frames):
            clock.wait_until(i / fps)
            t = clock.now()
            if t <= last_t:
                # Guarantee strictly-increasing sensor timestamps.
                t = last_t + 1e-6
            drone.update_to(t)
            state = drone.get_state()
            frame = frame_source.get_frame(state)
            if frame is None:
                missing.append(i)
                log(f"WARNING: missing frame at index {i} (t={t:.4f}s)")
                continue
            rel = _frame_rel_path(len(frame_paths))
            # IMPORTANT: save the RAW frame only. No telemetry overlay in rgb/.
            save_png_rgb(np.asarray(frame, dtype=np.uint8), output_dir / rel)
            frame_paths.append(rel)
            timestamps.append(t)
            states.append(dict(state))
            last_t = t
    finally:
        frame_source.stop()

    result = RecordResult(
        output_dir=output_dir,
        frame_paths=frame_paths,
        timestamps=np.asarray(timestamps, dtype=np.float64),
        states=states,
        width=width,
        height=height,
        missing_frames=missing,
    )
    write_rgb_timestamps_csv(result, meta_dir / "rgb_timestamps.csv")
    write_raw_state_log_csv(result, meta_dir / "raw_state_log.csv")
    log(f"Recorded {result.frame_count} frames over {result.duration_s:.3f}s -> {output_dir}")
    return result
