"""Training/evaluation episode construction for the RL-gated ensemble.

Backends are deterministic given a sequence, so they run once per sequence and
their trajectories are sliced into overlapping time windows. Each window
becomes one episode: measurements are position-rebased to the ground-truth
pose at the window start (the backend "was correct at episode start and then
drifts"), and the EKF is initialised from ground truth exactly like the
benchmark runner does for full sequences.
"""

from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from nav_benchmark.baselines.event_imu import EventImuBackend, EventImuConfig
from nav_benchmark.baselines.image_imu import ImageImuBackend, ImageImuConfig
from nav_benchmark.baselines.imu import ImuOnlyConfig
from nav_benchmark.baselines.multimodal_vio import MultimodalVioBackend, MultimodalVioConfig
from nav_benchmark.baselines.visual import EventVoBackend, FeatureVoConfig, RgbVoBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.events import ensure_event_frames
from nav_benchmark.rl.features import JepaObsSeries
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

MEASUREMENT_METHODS = ("event_imu", "event_vo", "image_imu", "multimodal_vio", "rgb_vo")

_RGB_SCALE_BIAS = 1.01
_EVENT_SCALE_BIAS = 0.98
_DEFAULT_GRAVITY = np.array([0.0, 0.0, 9.81], dtype=np.float64)


@dataclass
class EnsembleInputs:
    """One sequence's IMU stream plus every measurement backend's trajectory."""

    imu: np.ndarray
    backend_trajectories: dict[str, Trajectory]
    imu_config: ImuOnlyConfig
    gt_poses: np.ndarray


@dataclass
class FusionEpisode:
    """One rebased fusion window with dense ground truth for rewards."""

    name: str
    t_start: float
    t_end: float
    imu: np.ndarray
    backend_trajectories: dict[str, Trajectory]
    initial_position: np.ndarray
    initial_velocity: np.ndarray
    initial_orientation_xyzw: np.ndarray
    gt_timestamps: np.ndarray
    gt_positions: np.ndarray
    jepa_series: JepaObsSeries | None = None


def _gt_arrays(gt_poses: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = np.asarray(gt_poses["t"], dtype=np.float64)
    positions = np.stack([gt_poses["x"], gt_poses["y"], gt_poses["z"]], axis=1).astype(np.float64)
    quats = np.stack([gt_poses["qx"], gt_poses["qy"], gt_poses["qz"], gt_poses["qw"]], axis=1).astype(np.float64)
    norms = np.linalg.norm(quats, axis=1, keepdims=True)
    quats = np.divide(quats, norms, out=np.tile([[0.0, 0.0, 0.0, 1.0]], (len(quats), 1)), where=norms > 0.0)
    return t, positions, quats


def _interp_positions(source_t: np.ndarray, positions: np.ndarray, target_t: np.ndarray) -> np.ndarray:
    return np.stack([np.interp(target_t, source_t, positions[:, axis]) for axis in range(3)], axis=1)


def _interp_orientation(source_t: np.ndarray, quats: np.ndarray, query_t: float) -> np.ndarray:
    if len(source_t) < 2:
        return quats[0]
    clipped = float(np.clip(query_t, source_t[0], source_t[-1]))
    return Slerp(source_t, Rotation.from_quat(quats))(clipped).as_quat()


def _imu_config_from_ground_truth(gt_poses: np.ndarray, gravity: np.ndarray) -> ImuOnlyConfig:
    config = ImuOnlyConfig()
    gt_t, gt_positions, gt_quats = _gt_arrays(gt_poses)
    config.gravity = np.asarray(gravity, dtype=np.float64)
    config.initial_position = gt_positions[0].copy()
    config.initial_orientation = gt_quats[0].copy()
    velocity = np.zeros(3, dtype=np.float64)
    if len(gt_t) >= 2 and gt_t[1] > gt_t[0]:
        velocity = (gt_positions[1] - gt_positions[0]) / (gt_t[1] - gt_t[0])
    config.initial_velocity = velocity
    return config


def _required_episode_sources(sequence: MvsecSequence) -> tuple[np.ndarray, np.ndarray]:
    if sequence.imu is None or len(sequence.imu) == 0:
        raise ValueError("RL episode construction requires IMU data")
    if sequence.gt_poses is None or len(sequence.gt_poses) < 2:
        raise ValueError("RL episode construction requires ground-truth poses (rewards need them)")
    return sequence.imu, sequence.gt_poses


def _gravity_vector(gravity: np.ndarray | None) -> np.ndarray:
    if gravity is None:
        return _DEFAULT_GRAVITY.copy()
    return np.asarray(gravity, dtype=np.float64)


def _measurement_trajectories(
    sequence: MvsecSequence,
    imu_config: ImuOnlyConfig,
    event_window_sec: float,
) -> dict[str, Trajectory]:
    rgb_vo_config = FeatureVoConfig(scale_bias=_RGB_SCALE_BIAS)
    event_vo_config = FeatureVoConfig(scale_bias=_EVENT_SCALE_BIAS)
    return {
        "rgb_vo": RgbVoBackend().run(sequence, config=rgb_vo_config),
        "event_vo": EventVoBackend().run(sequence, config=event_vo_config),
        "event_imu": EventImuBackend().run(
            sequence, config=EventImuConfig(imu_config=imu_config, event_window_sec=event_window_sec)
        ),
        "image_imu": ImageImuBackend().run(
            sequence, config=ImageImuConfig(imu_config=imu_config, rgb_vo_config=rgb_vo_config)
        ),
        "multimodal_vio": MultimodalVioBackend().run(
            sequence,
            config=MultimodalVioConfig(
                imu_config=imu_config, rgb_vo_config=rgb_vo_config, event_vo_config=event_vo_config
            ),
        ),
    }


def compute_ensemble_inputs(
    sequence: MvsecSequence,
    *,
    event_window_sec: float = 0.05,
    gravity: np.ndarray | None = None,
) -> EnsembleInputs:
    """Run every measurement backend once and package the fusion inputs."""
    imu, gt_poses = _required_episode_sources(sequence)
    ensure_event_frames(sequence, window_sec=event_window_sec)

    imu_config = _imu_config_from_ground_truth(gt_poses, _gravity_vector(gravity))
    return EnsembleInputs(
        imu=imu,
        backend_trajectories=_measurement_trajectories(sequence, imu_config, event_window_sec),
        imu_config=imu_config,
        gt_poses=gt_poses,
    )


def _slice_imu(imu: np.ndarray, t0: float, t1: float) -> np.ndarray:
    t = np.asarray(imu["t"], dtype=np.float64)
    mask = (t >= t0) & (t <= t1)
    window = imu[mask].copy()
    if len(window) < 2:
        raise ValueError(f"IMU window [{t0:.3f}, {t1:.3f}] has fewer than two samples")
    return window


def _slice_trajectory(trajectory: Trajectory, t0: float, t1: float) -> Trajectory:
    t = np.asarray(trajectory.timestamps, dtype=np.float64)
    mask = (t >= t0) & (t <= t1)
    count = int(np.count_nonzero(mask))
    confidence = trajectory.confidence if trajectory.confidence is not None else np.ones(len(t))
    health = (
        trajectory.health if trajectory.health is not None else np.array([PoseHealth.OK.value] * len(t), dtype=object)
    )
    return Trajectory(
        timestamps=t[mask].copy(),
        method=trajectory.method,
        positions=trajectory.positions[mask].copy().reshape(count, 3),
        orientations=trajectory.orientations[mask].copy().reshape(count, 4),
        velocities=trajectory.velocities[mask].copy() if trajectory.velocities is not None else None,
        confidence=np.asarray(confidence, dtype=np.float64)[mask].copy(),
        health=np.asarray(health, dtype=object)[mask].copy(),
    )


def _rebase_trajectory(window: Trajectory, source: Trajectory, t0: float, gt_position_at_t0: np.ndarray) -> None:
    """Shift window positions so the backend agrees with ground truth at ``t0``."""
    if len(window.timestamps) == 0 or len(source.timestamps) == 0:
        return
    source_t = np.asarray(source.timestamps, dtype=np.float64)
    anchor = _interp_positions(source_t, source.positions, np.array([t0]))[0]
    window.positions += gt_position_at_t0 - anchor


def _slice_jepa_series(series: JepaObsSeries | None, t0: float, t1: float) -> JepaObsSeries | None:
    if series is None:
        return None
    mask = (series.times >= t0) & (series.times <= t1)
    return JepaObsSeries(
        times=series.times[mask].copy(),
        rgb_surprise=series.rgb_surprise[mask].copy(),
        event_surprise=series.event_surprise[mask].copy(),
        embedding_speed=series.embedding_speed[mask].copy(),
    )


def _window_bounds(t_start: float, t_end: float, window_sec: float, stride_sec: float) -> list[tuple[float, float]]:
    if window_sec <= 0.0 or stride_sec <= 0.0:
        raise ValueError("window_sec and stride_sec must be positive")
    if window_sec >= t_end - t_start:
        return [(t_start, t_end)]
    bounds: list[tuple[float, float]] = []
    t0 = t_start
    while t0 + window_sec <= t_end + 1e-9:
        bounds.append((t0, min(t0 + window_sec, t_end)))
        t0 += stride_sec
    return bounds


def build_episodes(
    inputs: EnsembleInputs,
    *,
    window_sec: float,
    stride_sec: float,
    name_prefix: str,
    jepa_series: JepaObsSeries | None = None,
) -> list[FusionEpisode]:
    """Slice one sequence's fusion inputs into rebased, GT-annotated episodes."""
    imu_t = np.asarray(inputs.imu["t"], dtype=np.float64)
    gt_t, gt_positions, gt_quats = _gt_arrays(inputs.gt_poses)
    t_start = max(float(imu_t[0]), float(gt_t[0]))
    t_end = min(float(imu_t[-1]), float(gt_t[-1]))
    if t_end <= t_start:
        raise ValueError("IMU and ground-truth time ranges do not overlap")

    episodes: list[FusionEpisode] = []
    for t0, t1 in _window_bounds(t_start, t_end, window_sec, stride_sec):
        imu_window = _slice_imu(inputs.imu, t0, t1)
        window_times = np.asarray(imu_window["t"], dtype=np.float64)
        gt_dense = _interp_positions(gt_t, gt_positions, window_times)
        gt_at_t0 = gt_dense[0]

        backends: dict[str, Trajectory] = {}
        for method, trajectory in inputs.backend_trajectories.items():
            window = _slice_trajectory(trajectory, t0, t1)
            _rebase_trajectory(window, trajectory, t0, gt_at_t0)
            backends[method] = window

        dt0 = window_times[1] - window_times[0]
        initial_velocity = (gt_dense[1] - gt_dense[0]) / dt0 if dt0 > 0.0 else np.zeros(3)
        episodes.append(
            FusionEpisode(
                name=f"{name_prefix}[{t0:.2f}s-{t1:.2f}s]",
                t_start=t0,
                t_end=t1,
                imu=imu_window,
                backend_trajectories=backends,
                initial_position=gt_at_t0.copy(),
                initial_velocity=np.asarray(initial_velocity, dtype=np.float64),
                initial_orientation_xyzw=_interp_orientation(gt_t, gt_quats, t0),
                gt_timestamps=window_times.copy(),
                gt_positions=gt_dense,
                jepa_series=_slice_jepa_series(jepa_series, t0, t1),
            )
        )
    return episodes
