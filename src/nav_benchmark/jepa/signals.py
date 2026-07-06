"""Per-frame JEPA signals and their projection onto the RL observation series.

Surprise (prediction error) and embedding speed are computed per stream (RGB
frames, event frames) with IMU-only propagation as the ego-motion reference —
never ground truth — so the exact same code path runs at training and
benchmark inference time.
"""

from dataclasses import dataclass

import numpy as np

from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.jepa.frames import ego_motion_features, stack_frame_patches
from nav_benchmark.jepa.model import JepaModel, embedding_speeds, surprise_scores
from nav_benchmark.rl.features import JepaObsSeries


@dataclass(frozen=True)
class FrameSignals:
    """Signals for one frame stream, aligned to its frame timestamps."""

    times: np.ndarray
    surprise: np.ndarray
    embedding_speed: np.ndarray


def imu_reference_trajectory(sequence: MvsecSequence, gravity: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """GT-free ego-motion reference: IMU-only propagation from a zero state."""
    config = ImuOnlyConfig()
    config.gravity = np.asarray(gravity, dtype=np.float64)
    trajectory = ImuOnlyBackend().run(sequence, config=config)
    return trajectory.timestamps, trajectory.positions, trajectory.orientations


def stream_signals(
    model: JepaModel,
    frames: np.ndarray,
    frame_times: np.ndarray,
    reference: tuple[np.ndarray, np.ndarray, np.ndarray],
    *,
    device: str = "cpu",
) -> FrameSignals:
    """Surprise and embedding speed for one frame stream."""
    patches = stack_frame_patches(frames)
    ego = ego_motion_features(reference[0], reference[1], reference[2], frame_times)
    return FrameSignals(
        times=np.asarray(frame_times, dtype=np.float64),
        surprise=surprise_scores(model, patches, ego, device=device),
        embedding_speed=embedding_speeds(model, patches, device=device),
    )


def _forward_fill(source_times: np.ndarray, source_values: np.ndarray, target_times: np.ndarray) -> np.ndarray:
    indices = np.searchsorted(source_times, target_times, side="right") - 1
    values = np.zeros(len(target_times), dtype=np.float64)
    valid = indices >= 0
    values[valid] = source_values[indices[valid]]
    return values


def combine_stream_signals(rgb: FrameSignals | None, event: FrameSignals | None) -> JepaObsSeries:
    """Merge per-stream signals onto one causal time base for observations."""
    streams = [s for s in (rgb, event) if s is not None and len(s.times) > 0]
    if not streams:
        raise ValueError("At least one non-empty frame stream is required for JEPA signals")
    times = np.unique(np.concatenate([s.times for s in streams]))
    rgb_surprise = _forward_fill(rgb.times, rgb.surprise, times) if rgb is not None else np.zeros(len(times))
    event_surprise = _forward_fill(event.times, event.surprise, times) if event is not None else np.zeros(len(times))
    speeds = [_forward_fill(s.times, s.embedding_speed, times) for s in streams]
    return JepaObsSeries(
        times=times,
        rgb_surprise=rgb_surprise,
        event_surprise=event_surprise,
        embedding_speed=np.mean(np.stack(speeds, axis=0), axis=0),
    )


def _sequence_stream(sequence: MvsecSequence, stream: str) -> tuple[np.ndarray, np.ndarray] | None:
    if stream == "rgb":
        frames, times = sequence.images, sequence.image_timestamps
    else:
        frames, times = sequence.event_frames, sequence.event_frame_timestamps
    if frames is None or times is None or len(frames) < 2:
        return None
    return np.asarray(frames), np.asarray(times, dtype=np.float64)


def obs_series_for_sequence(
    model: JepaModel,
    sequence: MvsecSequence,
    *,
    gravity: np.ndarray,
    device: str = "cpu",
) -> JepaObsSeries:
    """JEPA observation series for a loaded sequence (RGB and/or event frames)."""
    reference = imu_reference_trajectory(sequence, gravity)
    rgb_stream = _sequence_stream(sequence, "rgb")
    event_stream = _sequence_stream(sequence, "events")
    rgb = stream_signals(model, rgb_stream[0], rgb_stream[1], reference, device=device) if rgb_stream else None
    event = stream_signals(model, event_stream[0], event_stream[1], reference, device=device) if event_stream else None
    return combine_stream_signals(rgb, event)
