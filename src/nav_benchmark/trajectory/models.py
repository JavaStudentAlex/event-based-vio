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
        if self.health is not None:
            valid_states = {h.value for h in PoseHealth}
            for i, h in enumerate(self.health):
                h_str = str(h)
                if h_str not in valid_states:
                    raise ValueError(f"Invalid health value at index {i}: {h_str}. Must be one of {valid_states}")

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

    def __post_init__(self) -> None:
        self._validate_non_negative()
        self._validate_sums()
        self._validate_timestamps()

    def _validate_non_negative(self) -> None:
        if self.source_count < 0:
            raise ValueError("source_count must be non-negative")
        if self.target_count < 0:
            raise ValueError("target_count must be non-negative")
        if self.matched_count < 0:
            raise ValueError("matched_count must be non-negative")
        if self.unmatched_source_count < 0:
            raise ValueError("unmatched_source_count must be non-negative")
        if self.unmatched_target_count < 0:
            raise ValueError("unmatched_target_count must be non-negative")
        if self.tolerance_sec < 0:
            raise ValueError("tolerance_sec must be non-negative")
        if not (0.0 <= self.overlap_sufficiency <= 1.0):
            raise ValueError("overlap_sufficiency must be between 0.0 and 1.0")

    def _validate_sums(self) -> None:
        if self.source_count != self.matched_count + self.unmatched_source_count:
            raise ValueError("source_count must equal matched_count + unmatched_source_count")
        if self.target_count != self.matched_count + self.unmatched_target_count:
            raise ValueError("target_count must equal matched_count + unmatched_target_count")

    def _validate_timestamps(self) -> None:
        if self.matched_count == 0:
            if self.first_matched_timestamp is not None or self.last_matched_timestamp is not None:
                raise ValueError("first/last matched timestamps must be None when matched_count is 0")
        else:
            if self.first_matched_timestamp is None or self.last_matched_timestamp is None:
                raise ValueError("first/last matched timestamps must not be None when matched_count > 0")
            if self.first_matched_timestamp > self.last_matched_timestamp:
                raise ValueError("first_matched_timestamp must be <= last_matched_timestamp")


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

    def __post_init__(self) -> None:
        self._validate_required_fields()
        self._validate_numeric_fields()

    def _validate_required_fields(self) -> None:
        if not self.timestamp_unit:
            raise ValueError("timestamp_unit must not be empty")
        if not self.association_policy:
            raise ValueError("association_policy must not be empty")
        if not self.source_frame:
            raise ValueError("source_frame must not be empty")
        if not self.target_frame:
            raise ValueError("target_frame must not be empty")
        if not self.position_units:
            raise ValueError("position_units must not be empty")
        if not self.orientation_format:
            raise ValueError("orientation_format must not be empty")

    def _validate_numeric_fields(self) -> None:
        if self.association_tolerance_sec is not None and self.association_tolerance_sec < 0:
            raise ValueError("association_tolerance_sec must be non-negative")
        if self.tum_filtered_rows < 0:
            raise ValueError("tum_filtered_rows must be non-negative")
        for k, v in self.health_counts.items():
            if v < 0:
                raise ValueError(f"health count for {k} must be non-negative")
