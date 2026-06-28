import time
from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass(frozen=True)
class SampledTrajectory:
    positions: np.ndarray
    orientations: np.ndarray
    velocities: np.ndarray
    confidence: np.ndarray
    health: np.ndarray
    in_range: np.ndarray


def latency_per_sample_ms(start_time: float, count: int) -> np.ndarray:
    if count == 0:
        return np.empty(0, dtype=np.float64)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return np.full(count, elapsed_ms / count, dtype=np.float64)


def normalize_quaternions(quaternions: np.ndarray) -> np.ndarray:
    values = np.asarray(quaternions, dtype=np.float64).copy()
    if values.size == 0:
        return values.reshape((-1, 4))
    norms = np.linalg.norm(values, axis=1)
    valid = norms > 0.0
    values[valid] = values[valid] / norms[valid, np.newaxis]
    values[~valid] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return values


def velocities_from_positions(timestamps: np.ndarray, positions: np.ndarray) -> np.ndarray:
    timestamps = np.asarray(timestamps, dtype=np.float64)
    positions = np.asarray(positions, dtype=np.float64)
    velocities = np.zeros_like(positions)
    if len(timestamps) < 2:
        return velocities

    dt = np.diff(timestamps)
    dt[dt <= 0.0] = 1e-9
    step_velocities = np.diff(positions, axis=0) / dt[:, np.newaxis]
    velocities[:-1] = step_velocities
    velocities[-1] = step_velocities[-1]
    return velocities


def health_from_confidence(
    confidence: np.ndarray,
    *,
    ok_threshold: float = 0.55,
    degraded_threshold: float = 0.15,
) -> np.ndarray:
    health = np.empty(len(confidence), dtype=object)
    health[confidence >= ok_threshold] = PoseHealth.OK.value
    degraded_mask = (confidence >= degraded_threshold) & (confidence < ok_threshold)
    health[degraded_mask] = PoseHealth.DEGRADED.value
    health[confidence < degraded_threshold] = PoseHealth.LOST.value
    return health


def _gt_arrays(sequence: MvsecSequence) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if sequence.gt_poses is None or len(sequence.gt_poses) == 0:
        return None
    gt = sequence.gt_poses
    timestamps = np.asarray(gt["t"], dtype=np.float64)
    positions = np.stack([gt["x"], gt["y"], gt["z"]], axis=1).astype(np.float64)
    orientations = np.stack([gt["qx"], gt["qy"], gt["qz"], gt["qw"]], axis=1).astype(np.float64)
    return timestamps, positions, normalize_quaternions(orientations)


def sample_ground_truth(sequence: MvsecSequence, timestamps: np.ndarray) -> SampledTrajectory | None:
    arrays = _gt_arrays(sequence)
    if arrays is None:
        return None

    gt_t, gt_positions, gt_orientations = arrays
    target_t = np.asarray(timestamps, dtype=np.float64)
    if len(target_t) == 0:
        empty_positions = np.empty((0, 3), dtype=np.float64)
        empty_orientations = np.empty((0, 4), dtype=np.float64)
        return SampledTrajectory(
            positions=empty_positions,
            orientations=empty_orientations,
            velocities=empty_positions.copy(),
            confidence=np.empty(0, dtype=np.float64),
            health=np.empty(0, dtype=object),
            in_range=np.empty(0, dtype=bool),
        )

    positions = np.stack(
        [np.interp(target_t, gt_t, gt_positions[:, axis]) for axis in range(3)],
        axis=1,
    )

    if len(gt_t) >= 2:
        clipped_t = np.clip(target_t, gt_t[0], gt_t[-1])
        rotations = Rotation.from_quat(gt_orientations)
        orientations = Slerp(gt_t, rotations)(clipped_t).as_quat()
    else:
        orientations = np.repeat(gt_orientations[:1], len(target_t), axis=0)

    velocities = velocities_from_positions(target_t, positions)
    in_range = (target_t >= gt_t[0]) & (target_t <= gt_t[-1])
    return SampledTrajectory(
        positions=positions,
        orientations=normalize_quaternions(orientations),
        velocities=velocities,
        confidence=np.ones(len(target_t), dtype=np.float64),
        health=np.array([PoseHealth.OK.value] * len(target_t), dtype=object),
        in_range=in_range,
    )


def interpolate_trajectory(trajectory: Trajectory, timestamps: np.ndarray) -> SampledTrajectory:
    source_t = np.asarray(trajectory.timestamps, dtype=np.float64)
    target_t = np.asarray(timestamps, dtype=np.float64)
    if len(source_t) == 0:
        raise ValueError(f"Cannot interpolate empty trajectory: {trajectory.method}")

    positions = np.stack(
        [np.interp(target_t, source_t, trajectory.positions[:, axis]) for axis in range(3)],
        axis=1,
    )

    if len(source_t) >= 2:
        clipped_t = np.clip(target_t, source_t[0], source_t[-1])
        orientations = Slerp(source_t, Rotation.from_quat(normalize_quaternions(trajectory.orientations)))(
            clipped_t
        ).as_quat()
    else:
        orientations = np.repeat(trajectory.orientations[:1], len(target_t), axis=0)

    if trajectory.velocities is not None:
        velocities = np.stack(
            [np.interp(target_t, source_t, trajectory.velocities[:, axis]) for axis in range(3)],
            axis=1,
        )
    else:
        velocities = velocities_from_positions(target_t, positions)

    confidence = (
        np.interp(target_t, source_t, trajectory.confidence)
        if trajectory.confidence is not None
        else np.ones(len(target_t), dtype=np.float64)
    )

    source_health = (
        np.array([str(value) for value in trajectory.health], dtype=object)
        if trajectory.health is not None
        else np.array([PoseHealth.OK.value] * len(source_t), dtype=object)
    )
    nearest = np.searchsorted(source_t, target_t, side="left")
    nearest = np.clip(nearest, 0, len(source_t) - 1)
    previous = np.clip(nearest - 1, 0, len(source_t) - 1)
    use_previous = np.abs(target_t - source_t[previous]) <= np.abs(target_t - source_t[nearest])
    nearest[use_previous] = previous[use_previous]
    health = source_health[nearest]

    in_range = (target_t >= source_t[0]) & (target_t <= source_t[-1])
    confidence = np.where(in_range, confidence, 0.0)
    health = np.where(in_range, health, PoseHealth.INVALID.value)

    return SampledTrajectory(
        positions=positions,
        orientations=normalize_quaternions(orientations),
        velocities=velocities,
        confidence=np.clip(confidence, 0.0, 1.0),
        health=health,
        in_range=in_range,
    )
