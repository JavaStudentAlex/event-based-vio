import time
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial.transform import Rotation

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass
class ImuOnlyConfig:
    """
    Configuration for IMU-only propagation backend.
    """

    gravity: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 9.81]))
    initial_position: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0]))
    initial_orientation: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0, 1.0]))  # xyzw
    initial_velocity: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0]))
    degraded_time_threshold: float = 5.0
    lost_time_threshold: float = 10.0
    degraded_drift_threshold: float = 50.0
    lost_drift_threshold: float = 100.0

    def __post_init__(self) -> None:
        self.gravity = np.asarray(self.gravity, dtype=np.float64)
        self.initial_position = np.asarray(self.initial_position, dtype=np.float64)
        self.initial_orientation = np.asarray(self.initial_orientation, dtype=np.float64)
        self.initial_velocity = np.asarray(self.initial_velocity, dtype=np.float64)


def _require_imu(sequence: MvsecSequence):
    if sequence.imu is None or len(sequence.imu) == 0:
        raise ValueError("IMU data is missing or empty in the sequence")
    return sequence.imu


def _initial_state_arrays(count: int, config: ImuOnlyConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    positions = np.zeros((count, 3), dtype=np.float64)
    orientations = np.zeros((count, 4), dtype=np.float64)
    velocities = np.zeros((count, 3), dtype=np.float64)
    health = np.empty(count, dtype=object)
    positions[0] = config.initial_position
    orientations[0] = config.initial_orientation
    velocities[0] = config.initial_velocity
    health[0] = PoseHealth.OK.value
    return positions, orientations, velocities, health


def _positive_dt(timestamps: np.ndarray, index: int) -> float:
    dt = timestamps[index + 1] - timestamps[index]
    return float(dt) if dt > 0 else 1e-6


def _integrated_orientation(orientation: np.ndarray, omega: np.ndarray, dt: float) -> Rotation:
    return Rotation.from_quat(orientation) * Rotation.from_rotvec(omega * dt)


def _body_acceleration(imu, index: int) -> np.ndarray:
    return np.array([imu["ax"][index], imu["ay"][index], imu["az"][index]], dtype=np.float64)


def _angular_velocity(imu, index: int) -> np.ndarray:
    return np.array([imu["gx"][index], imu["gy"][index], imu["gz"][index]], dtype=np.float64)


def _is_lost(current_health: str, elapsed: float, distance: float, config: ImuOnlyConfig) -> bool:
    return (
        current_health == PoseHealth.LOST.value
        or elapsed > config.lost_time_threshold
        or distance > config.lost_drift_threshold
    )


def _is_degraded(current_health: str, elapsed: float, distance: float, config: ImuOnlyConfig) -> bool:
    return (
        current_health == PoseHealth.DEGRADED.value
        or elapsed > config.degraded_time_threshold
        or distance > config.degraded_drift_threshold
    )


def _next_imu_health(current_health: str, elapsed: float, distance: float, config: ImuOnlyConfig) -> str:
    if _is_lost(current_health, elapsed, distance, config):
        return PoseHealth.LOST.value
    if _is_degraded(current_health, elapsed, distance, config):
        return PoseHealth.DEGRADED.value
    return PoseHealth.OK.value


def _latency_metric(start_time: float, count: int) -> np.ndarray:
    total_time_ms = (time.perf_counter() - start_time) * 1000.0
    return np.full(count, total_time_ms / count, dtype=np.float64)


class ImuOnlyBackend(BaseOdometryBackend):
    """
    Inertial navigation baseline (open-loop gyro/accel integration with gravity removal).
    """

    method = "imu_only"
    required_streams = ("imu",)

    def run(self, sequence: MvsecSequence, *, config: ImuOnlyConfig | None = None) -> Trajectory:
        """
        Runs IMU-only propagation on the sequence.
        """
        imu = _require_imu(sequence)
        cfg = config if config is not None else ImuOnlyConfig()
        t = imu["t"]
        N = len(t)
        positions, orientations, velocities, health = _initial_state_arrays(N, cfg)

        # Track execution time for latency metric
        start_time = time.perf_counter()

        current_health = PoseHealth.OK.value
        t0 = t[0]

        for i in range(N - 1):
            dt = _positive_dt(t, i)
            v_curr = velocities[i]
            p_curr = positions[i]

            R_curr = Rotation.from_quat(orientations[i])
            R_next = _integrated_orientation(orientations[i], _angular_velocity(imu, i), dt)
            orientations[i + 1] = R_next.as_quat()

            a_world = R_curr.apply(_body_acceleration(imu, i)) - cfg.gravity
            v_next = v_curr + a_world * dt
            p_next = p_curr + v_curr * dt + 0.5 * a_world * (dt**2)

            velocities[i + 1] = v_next
            positions[i + 1] = p_next

            # Update health status
            dt_elapsed = t[i + 1] - t0
            dist = np.linalg.norm(p_next - cfg.initial_position)
            next_health = _next_imu_health(current_health, dt_elapsed, dist, cfg)
            health[i + 1] = next_health
            current_health = next_health

        latency_ms = _latency_metric(start_time, N)
        confidence = np.ones(N, dtype=np.float64)

        return Trajectory(
            timestamps=t,
            method="imu_only",
            positions=positions,
            orientations=orientations,
            velocities=velocities,
            confidence=confidence,
            health=health,
            latency_ms=latency_ms,
        )
