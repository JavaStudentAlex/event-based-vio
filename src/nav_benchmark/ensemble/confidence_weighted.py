import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from nav_benchmark.baselines.common import interpolate_trajectory, normalize_quaternions
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

ENSEMBLE_METHODS = ("imu_only", "rgb_vo", "event_vo", "event_imu")
ENSEMBLE_WEIGHT_COLUMNS = {
    "imu_only": "w_imu",
    "rgb_vo": "w_rgb",
    "event_vo": "w_event",
    "event_imu": "w_event_imu",
}


@dataclass
class EnsembleConfig:
    """Configuration for confidence-weighted deterministic ensemble fusion."""

    static_weights: dict[str, float] = field(
        default_factory=lambda: {
            "event_imu": 0.50,
            "rgb_vo": 0.25,
            "event_vo": 0.15,
            "imu_only": 0.10,
        }
    )
    preferred_timestamp_method: str = "event_imu"
    min_total_reliability: float = 1e-9
    degraded_health_multiplier: float = 0.45
    failed_health_multiplier: float = 0.0


def _health_multiplier(health: np.ndarray, config: EnsembleConfig) -> np.ndarray:
    labels = np.array([str(value) for value in health], dtype=object)
    multiplier = np.ones(len(labels), dtype=np.float64)
    multiplier[labels == PoseHealth.DEGRADED.value] = config.degraded_health_multiplier
    multiplier[np.isin(labels, [PoseHealth.LOST.value, PoseHealth.INVALID.value])] = config.failed_health_multiplier
    return multiplier


def _target_timestamps(trajectories: dict[str, Trajectory], config: EnsembleConfig) -> np.ndarray:
    preferred = trajectories.get(config.preferred_timestamp_method)
    if preferred is not None:
        return preferred.timestamps

    best_method = max(
        trajectories,
        key=lambda method: config.static_weights.get(method, 0.0),
    )
    return trajectories[best_method].timestamps


def _normalized_weight_columns(
    trajectories: dict[str, Trajectory],
    timestamps: np.ndarray,
    config: EnsembleConfig,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    sampled = {method: interpolate_trajectory(trajectory, timestamps) for method, trajectory in trajectories.items()}
    raw_weights: dict[str, np.ndarray] = {}
    for method, sampled_trajectory in sampled.items():
        static = float(config.static_weights.get(method, 0.0))
        raw = static * sampled_trajectory.confidence * _health_multiplier(sampled_trajectory.health, config)
        raw_weights[method] = np.clip(raw, 0.0, None)

    total = np.zeros(len(timestamps), dtype=np.float64)
    for raw in raw_weights.values():
        total += raw

    normalized: dict[str, np.ndarray] = {}
    for method in ENSEMBLE_METHODS:
        raw = raw_weights.get(method, np.zeros(len(timestamps), dtype=np.float64))
        normalized[method] = np.divide(
            raw,
            total,
            out=np.zeros_like(raw),
            where=total > config.min_total_reliability,
        )

    no_reliable_input = total <= config.min_total_reliability
    if np.any(no_reliable_input):
        fallback = "imu_only" if "imu_only" in trajectories else next(iter(trajectories))
        normalized[fallback][no_reliable_input] = 1.0

    return normalized, {method: sampled_trajectory.__dict__ for method, sampled_trajectory in sampled.items()}


def _blend_quaternions(
    sampled: dict[str, dict[str, np.ndarray]], weights: dict[str, np.ndarray], count: int
) -> np.ndarray:
    blended = np.zeros((count, 4), dtype=np.float64)
    reference: np.ndarray | None = None
    for method in ENSEMBLE_METHODS:
        data = sampled.get(method)
        if data is None:
            continue
        orientations = data["orientations"]
        if reference is None:
            reference = orientations.copy()
        aligned = orientations.copy()
        dots = np.sum(aligned * reference, axis=1)
        aligned[dots < 0.0] *= -1.0
        blended += weights[method][:, np.newaxis] * aligned

    zero = np.linalg.norm(blended, axis=1) <= 1e-9
    blended[zero] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return normalize_quaternions(blended)


def fuse_trajectories(
    trajectories: dict[str, Trajectory],
    *,
    config: EnsembleConfig | None = None,
) -> Trajectory:
    """Fuse standardized baseline outputs into one confidence-weighted ensemble trajectory."""
    if len(trajectories) < 2:
        raise ValueError("Ensemble fusion requires at least two input trajectories")

    cfg = config if config is not None else EnsembleConfig()
    unknown_methods = set(trajectories) - set(ENSEMBLE_METHODS)
    if unknown_methods:
        raise ValueError(f"Unsupported ensemble input method(s): {sorted(unknown_methods)}")

    timestamps = _target_timestamps(trajectories, cfg)
    count = len(timestamps)
    weights, sampled = _normalized_weight_columns(trajectories, timestamps, cfg)

    positions = np.zeros((count, 3), dtype=np.float64)
    velocities = np.zeros((count, 3), dtype=np.float64)
    confidence = np.zeros(count, dtype=np.float64)
    for method in ENSEMBLE_METHODS:
        data = sampled.get(method)
        if data is None:
            continue
        method_weight = weights[method][:, np.newaxis]
        positions += method_weight * data["positions"]
        velocities += method_weight * data["velocities"]
        confidence += weights[method] * data["confidence"]

    orientations = _blend_quaternions(sampled, weights, count)
    health = np.empty(count, dtype=object)
    health[confidence >= 0.55] = PoseHealth.OK.value
    degraded = (confidence >= 0.15) & (confidence < 0.55)
    health[degraded] = PoseHealth.DEGRADED.value
    health[confidence < 0.15] = PoseHealth.LOST.value

    extra_columns = {
        ENSEMBLE_WEIGHT_COLUMNS[method]: weights[method]
        for method in ENSEMBLE_METHODS
        if method in ENSEMBLE_WEIGHT_COLUMNS
    }

    return Trajectory(
        timestamps=np.asarray(timestamps, dtype=np.float64),
        method="ensemble",
        positions=positions,
        orientations=orientations,
        velocities=velocities,
        confidence=np.clip(confidence, 0.0, 1.0),
        health=health,
        latency_ms=np.zeros(count, dtype=np.float64),
        extra_columns=extra_columns,
    )


def write_weight_log_csv(trajectory: Trajectory, path: str | Path) -> None:
    """Write ensemble weight columns to a compact CSV for plotting/debugging."""
    missing = [column for column in ENSEMBLE_WEIGHT_COLUMNS.values() if column not in trajectory.extra_columns]
    if missing:
        raise ValueError(f"Trajectory is missing ensemble weight columns: {missing}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        columns = ["timestamp", *ENSEMBLE_WEIGHT_COLUMNS.values()]
        writer.writerow(columns)
        for i, timestamp in enumerate(trajectory.timestamps):
            writer.writerow(
                [
                    f"{float(timestamp):.9f}",
                    *[
                        f"{float(trajectory.extra_columns[column][i]):.9f}"
                        for column in ENSEMBLE_WEIGHT_COLUMNS.values()
                    ],
                ]
            )
