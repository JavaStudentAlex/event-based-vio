"""Wrapper backend for trajectories produced by external SLAM/VIO tools.

This is the integration path for strong external baselines such as
UltimateSLAM or ESVO: run the external tool offline, then feed its exported
trajectory (TUM or project CSV) through this backend so it flows through the
same export/evaluation/validation contract as native methods.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.export import read_tum_trajectory
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass
class ExternalTrajectoryConfig:
    """Configuration for normalizing an externally produced trajectory."""

    trajectory_path: str | Path = ""
    format: str = "auto"  # "tum", "csv", or "auto" (by file extension)
    default_confidence: float = 0.8
    gap_degraded_sec: float = 0.5


def _resolve_format(path: Path, declared: str) -> str:
    if declared != "auto":
        return declared
    return "csv" if path.suffix.lower() == ".csv" else "tum"


def _gap_health(timestamps: np.ndarray, gap_degraded_sec: float) -> np.ndarray:
    """Mark samples that follow a timestamp gap larger than the threshold as DEGRADED."""
    health = np.array([PoseHealth.OK.value] * len(timestamps), dtype=object)
    if len(timestamps) > 1:
        gaps = np.diff(timestamps)
        health[1:][gaps > gap_degraded_sec] = PoseHealth.DEGRADED.value
    return health


def _from_tum(path: Path, config: ExternalTrajectoryConfig) -> Trajectory:
    trajectory = read_tum_trajectory(path, method="external")
    count = len(trajectory.timestamps)
    return Trajectory(
        timestamps=trajectory.timestamps,
        method="external",
        positions=trajectory.positions,
        orientations=trajectory.orientations,
        confidence=np.full(count, config.default_confidence),
        health=_gap_health(trajectory.timestamps, config.gap_degraded_sec),
        latency_ms=np.zeros(count),
    )


def _from_project_csv(path: Path) -> Trajectory:
    from nav_benchmark.evaluation.metrics import read_project_csv

    loaded = read_project_csv(path)
    return Trajectory(
        timestamps=loaded.timestamps,
        method="external",
        positions=loaded.positions,
        orientations=loaded.orientations,
        velocities=loaded.velocities,
        confidence=loaded.confidence,
        health=loaded.health,
        latency_ms=loaded.latency_ms,
    )


class ExternalTrajectoryBackend(BaseOdometryBackend):
    """Normalize an external tool's trajectory into the project backend contract."""

    method = "external"
    required_streams = ()

    def run(self, sequence: MvsecSequence, *, config: ExternalTrajectoryConfig | None = None) -> Trajectory:
        if config is None or not str(config.trajectory_path):
            raise ValueError("ExternalTrajectoryBackend requires a config with trajectory_path")

        path = Path(config.trajectory_path)
        if not path.exists():
            raise FileNotFoundError(f"External trajectory file not found: {path}")

        fmt = _resolve_format(path, config.format)
        if fmt == "csv":
            return _from_project_csv(path)
        if fmt == "tum":
            return _from_tum(path, config)
        raise ValueError(f"Unsupported external trajectory format: {fmt!r}")
