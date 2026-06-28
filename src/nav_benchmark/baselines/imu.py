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


class ImuOnlyBackend(BaseOdometryBackend):
    """
    Inertial navigation baseline (open-loop gyro/accel integration with gravity removal).
    """

    def run(self, sequence: MvsecSequence, *, config: ImuOnlyConfig | None = None) -> Trajectory:
        """
        Runs IMU-only propagation on the sequence.
        """
        if sequence.imu is None or len(sequence.imu) == 0:
            raise ValueError("IMU data is missing or empty in the sequence")

        cfg = config if config is not None else ImuOnlyConfig()

        imu = sequence.imu
        t = imu["t"]
        N = len(t)

        # Allocate arrays
        positions = np.zeros((N, 3), dtype=np.float64)
        orientations = np.zeros((N, 4), dtype=np.float64)
        velocities = np.zeros((N, 3), dtype=np.float64)
        health = np.empty(N, dtype=object)

        # Initialize initial state
        positions[0] = cfg.initial_position
        orientations[0] = cfg.initial_orientation
        velocities[0] = cfg.initial_velocity
        health[0] = PoseHealth.OK.value

        # Track execution time for latency metric
        start_time = time.perf_counter()

        current_health = PoseHealth.OK.value
        t0 = t[0]

        for i in range(N - 1):
            dt = t[i + 1] - t[i]
            if dt <= 0:
                dt = 1e-6  # safety fallback

            # Current state
            R_curr = Rotation.from_quat(orientations[i])
            v_curr = velocities[i]
            p_curr = positions[i]

            # Integrate orientation using angular velocity in body frame
            # We assume angular velocity is constant over dt
            omega = np.array([imu["gx"][i], imu["gy"][i], imu["gz"][i]], dtype=np.float64)
            rot_vec = omega * dt
            R_inc = Rotation.from_rotvec(rot_vec)
            R_next = R_curr * R_inc
            orientations[i + 1] = R_next.as_quat()

            # Accelerometer reading in body frame
            a_body = np.array([imu["ax"][i], imu["ay"][i], imu["az"][i]], dtype=np.float64)

            # Transform to world frame and remove gravity
            a_world = R_curr.apply(a_body) - cfg.gravity

            # Integrate velocity and position
            v_next = v_curr + a_world * dt
            p_next = p_curr + v_curr * dt + 0.5 * a_world * (dt ** 2)

            velocities[i + 1] = v_next
            positions[i + 1] = p_next

            # Update health status
            dt_elapsed = t[i + 1] - t0
            dist = np.linalg.norm(p_next - cfg.initial_position)

            if current_health == PoseHealth.LOST.value:
                # Sticky LOST status
                next_health = PoseHealth.LOST.value
            elif dt_elapsed > cfg.lost_time_threshold or dist > cfg.lost_drift_threshold:
                next_health = PoseHealth.LOST.value
            elif current_health == PoseHealth.DEGRADED.value:
                # Sticky DEGRADED status (unless degraded transitions to LOST)
                next_health = PoseHealth.DEGRADED.value
            elif dt_elapsed > cfg.degraded_time_threshold or dist > cfg.degraded_drift_threshold:
                next_health = PoseHealth.DEGRADED.value
            else:
                next_health = PoseHealth.OK.value

            health[i + 1] = next_health
            current_health = next_health

        # Compute latency
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        latency_per_sample = total_time_ms / N
        latency_ms = np.full(N, latency_per_sample, dtype=np.float64)
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
