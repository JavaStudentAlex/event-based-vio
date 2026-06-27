from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np


class PoseHealth(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    LOST = "LOST"
    INVALID = "INVALID"


@dataclass
class Trajectory:
    timestamps: np.ndarray
    method: str
    positions: np.ndarray  # (N, 3) -> x, y, z
    orientations: np.ndarray  # (N, 4) -> qx, qy, qz, qw
    velocities: np.ndarray | None = None  # (N, 3) -> vx, vy, vz
    confidence: np.ndarray | None = None  # (N,)
    health: np.ndarray | None = None  # (N,) object array of PoseHealth or str
    latency_ms: np.ndarray | None = None  # (N,)

    def __post_init__(self) -> None:
        self._validate_core()
        self._validate_opt_shapes()
        self._validate_opt_lens()

    def _validate_core(self) -> None:
        n = len(self.timestamps)
        if self.positions.shape != (n, 3):
            raise ValueError("Positions must be shape (N, 3)")
        if self.orientations.shape != (n, 4):
            raise ValueError("Orientations must be shape (N, 4)")

    def _validate_opt_shapes(self) -> None:
        n = len(self.timestamps)
        if self.velocities is not None and self.velocities.shape != (n, 3):
            raise ValueError("Velocities must be shape (N, 3)")

    def _validate_opt_lens(self) -> None:
        n = len(self.timestamps)
        self._check_len(self.confidence, n, "Confidence")
        self._check_len(self.health, n, "Health")
        self._check_len(self.latency_ms, n, "Latency")

    def _check_len(self, arr: Any, n: int, name: str) -> None:
        if arr is not None and len(arr) != n:
            raise ValueError(f"{name} must be shape (N,)")


@dataclass
class SyncDiagnostics:
    source_count: int
    target_count: int
    matched_count: int
    unmatched_source_count: int
    unmatched_target_count: int
    tolerance_sec: float
    first_matched_timestamp: float | None
    last_matched_timestamp: float | None
    overlap_sufficiency: float  # matched_count / max(source_count, target_count, 1)
    unmatched_source_ranges: list[tuple[float, float]] = field(default_factory=list)
    unmatched_target_ranges: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class ExportMetadata:
    timestamp_unit: str = "seconds"
    association_policy: str = "nearest_neighbor"
    association_tolerance_sec: float | None = None
    source_frame: str = "imu"
    target_frame: str = "world"
    position_units: str = "meters"
    orientation_format: str = "quaternion_xyzw"
    health_counts: dict[str, int] = field(default_factory=dict)
    tum_filtered_rows: int = 0
