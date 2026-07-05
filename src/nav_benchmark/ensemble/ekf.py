"""Error-state EKF for IMU propagation with absolute position updates.

State: position, velocity, orientation (xyzw quaternion), accelerometer bias,
gyroscope bias. The 15x15 covariance tracks the error state
``[dp, dv, dtheta, db_a, db_g]``.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial.transform import Rotation

_STATE_DIM = 15
_POS = slice(0, 3)
_VEL = slice(3, 6)
_THETA = slice(6, 9)
_BA = slice(9, 12)
_BG = slice(12, 15)


@dataclass
class EkfConfig:
    """Noise and prior configuration for the error-state EKF."""

    gravity: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 9.81]))
    accel_noise: float = 0.05  # m/s^2, white accelerometer noise
    gyro_noise: float = 0.005  # rad/s, white gyroscope noise
    accel_bias_rw: float = 0.0002  # m/s^3 sqrt-rate bias random walk
    gyro_bias_rw: float = 0.00002  # rad/s^2 sqrt-rate bias random walk
    initial_position_sigma: float = 1e-3
    initial_velocity_sigma: float = 0.1
    initial_orientation_sigma: float = 0.01
    initial_accel_bias_sigma: float = 0.02
    initial_gyro_bias_sigma: float = 0.002

    def __post_init__(self) -> None:
        self.gravity = np.asarray(self.gravity, dtype=np.float64)


def _skew(v: np.ndarray) -> np.ndarray:
    return np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ],
        dtype=np.float64,
    )


def _initial_covariance(config: EkfConfig) -> np.ndarray:
    sigmas = np.concatenate(
        [
            np.full(3, config.initial_position_sigma),
            np.full(3, config.initial_velocity_sigma),
            np.full(3, config.initial_orientation_sigma),
            np.full(3, config.initial_accel_bias_sigma),
            np.full(3, config.initial_gyro_bias_sigma),
        ]
    )
    return np.diag(sigmas**2)


def _transition_matrix(rotation: Rotation, accel_corrected: np.ndarray, dt: float) -> np.ndarray:
    R = rotation.as_matrix()
    F = np.eye(_STATE_DIM)
    F[_POS, _VEL] = np.eye(3) * dt
    F[_VEL, _THETA] = -R @ _skew(accel_corrected) * dt
    F[_VEL, _BA] = -R * dt
    F[_THETA, _BG] = -np.eye(3) * dt
    return F


def _process_noise(config: EkfConfig, dt: float) -> np.ndarray:
    Q = np.zeros((_STATE_DIM, _STATE_DIM))
    Q[_VEL, _VEL] = np.eye(3) * (config.accel_noise**2) * dt
    Q[_THETA, _THETA] = np.eye(3) * (config.gyro_noise**2) * dt
    Q[_BA, _BA] = np.eye(3) * (config.accel_bias_rw**2) * dt
    Q[_BG, _BG] = np.eye(3) * (config.gyro_bias_rw**2) * dt
    return Q


class ErrorStateEkf:
    """Strapdown IMU propagation with gated absolute position corrections."""

    def __init__(
        self,
        config: EkfConfig,
        *,
        initial_position: np.ndarray,
        initial_velocity: np.ndarray,
        initial_orientation_xyzw: np.ndarray,
    ) -> None:
        self.config = config
        self.position = np.asarray(initial_position, dtype=np.float64).copy()
        self.velocity = np.asarray(initial_velocity, dtype=np.float64).copy()
        self.orientation = Rotation.from_quat(np.asarray(initial_orientation_xyzw, dtype=np.float64))
        self.accel_bias = np.zeros(3, dtype=np.float64)
        self.gyro_bias = np.zeros(3, dtype=np.float64)
        self.P = _initial_covariance(config)

    @property
    def orientation_xyzw(self) -> np.ndarray:
        return self.orientation.as_quat()

    def position_covariance(self) -> np.ndarray:
        return self.P[_POS, _POS].copy()

    def position_sigma(self) -> float:
        """RMS 1-sigma position uncertainty across axes."""
        return float(np.sqrt(np.trace(self.P[_POS, _POS]) / 3.0))

    def propagate(self, accel_body: np.ndarray, gyro_body: np.ndarray, dt: float) -> None:
        """Advance the nominal state and covariance by one IMU sample."""
        if dt <= 0.0:
            return
        accel = np.asarray(accel_body, dtype=np.float64) - self.accel_bias
        gyro = np.asarray(gyro_body, dtype=np.float64) - self.gyro_bias

        accel_world = self.orientation.apply(accel) - self.config.gravity
        self.position = self.position + self.velocity * dt + 0.5 * accel_world * dt**2
        self.velocity = self.velocity + accel_world * dt
        next_orientation = self.orientation * Rotation.from_rotvec(gyro * dt)

        F = _transition_matrix(self.orientation, accel, dt)
        self.P = F @ self.P @ F.T + _process_noise(self.config, dt)
        self.orientation = next_orientation

    def innovation(self, measured_position: np.ndarray, sigma_position: float) -> tuple[np.ndarray, np.ndarray]:
        """Innovation vector and covariance for an absolute position measurement."""
        e = np.asarray(measured_position, dtype=np.float64) - self.position
        S = self.P[_POS, _POS] + np.eye(3) * sigma_position**2
        return e, S

    def update_position(self, measured_position: np.ndarray, sigma_position: float) -> None:
        """Apply an (already gated) absolute position measurement."""
        e, S = self.innovation(measured_position, sigma_position)
        H = np.zeros((3, _STATE_DIM))
        H[:, _POS] = np.eye(3)

        K = self.P @ H.T @ np.linalg.inv(S)
        dx = K @ e
        self._inject_error_state(dx)
        self.P = (np.eye(_STATE_DIM) - K @ H) @ self.P

    def _inject_error_state(self, dx: np.ndarray) -> None:
        self.position = self.position + dx[_POS]
        self.velocity = self.velocity + dx[_VEL]
        self.orientation = self.orientation * Rotation.from_rotvec(dx[_THETA])
        self.accel_bias = self.accel_bias + dx[_BA]
        self.gyro_bias = self.gyro_bias + dx[_BG]
