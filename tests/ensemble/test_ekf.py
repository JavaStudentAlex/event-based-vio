import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from nav_benchmark.ensemble.ekf import EkfConfig, ErrorStateEkf


def _make_ekf(**config_kwargs) -> ErrorStateEkf:
    return ErrorStateEkf(
        EkfConfig(**config_kwargs),
        initial_position=np.zeros(3),
        initial_velocity=np.zeros(3),
        initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
    )


class TestPropagation:
    def test_stationary_imu_stays_at_rest(self):
        ekf = _make_ekf()
        for _ in range(100):
            ekf.propagate(np.array([0.0, 0.0, 9.81]), np.zeros(3), dt=0.01)

        np.testing.assert_allclose(ekf.position, np.zeros(3), atol=1e-12)
        np.testing.assert_allclose(ekf.velocity, np.zeros(3), atol=1e-12)

    def test_constant_acceleration_integrates_position(self):
        ekf = _make_ekf()
        # 1 m/s^2 along x for 1 s in 100 steps: v = 1 m/s, p = 0.5 m (+ discretization).
        for _ in range(100):
            ekf.propagate(np.array([1.0, 0.0, 9.81]), np.zeros(3), dt=0.01)

        assert ekf.velocity[0] == pytest.approx(1.0, abs=1e-9)
        assert ekf.position[0] == pytest.approx(0.5, abs=0.01)

    def test_gyro_rotation_integrates_orientation(self):
        ekf = _make_ekf(gravity=np.zeros(3))
        # Rotate 90 degrees around z over 1 s.
        for _ in range(100):
            ekf.propagate(np.zeros(3), np.array([0.0, 0.0, np.pi / 2.0]), dt=0.01)

        yaw = Rotation.from_quat(ekf.orientation_xyzw).as_euler("zyx")[0]
        assert yaw == pytest.approx(np.pi / 2.0, abs=1e-6)

    def test_covariance_grows_without_updates(self):
        ekf = _make_ekf()
        initial_sigma = ekf.position_sigma()
        for _ in range(200):
            ekf.propagate(np.array([0.0, 0.0, 9.81]), np.zeros(3), dt=0.01)
        assert ekf.position_sigma() > initial_sigma

    def test_nonpositive_dt_is_ignored(self):
        ekf = _make_ekf()
        ekf.propagate(np.array([5.0, 0.0, 9.81]), np.zeros(3), dt=0.0)
        np.testing.assert_allclose(ekf.position, np.zeros(3))

    def test_accel_bias_is_subtracted(self):
        ekf = _make_ekf()
        ekf.accel_bias = np.array([1.0, 0.0, 0.0])
        for _ in range(10):
            ekf.propagate(np.array([1.0, 0.0, 9.81]), np.zeros(3), dt=0.01)
        np.testing.assert_allclose(ekf.velocity, np.zeros(3), atol=1e-12)


class TestPositionUpdate:
    def test_update_pulls_state_toward_measurement(self):
        ekf = _make_ekf()
        for _ in range(100):
            ekf.propagate(np.array([0.0, 0.0, 9.81]), np.zeros(3), dt=0.01)

        before = ekf.position.copy()
        target = np.array([1.0, 0.0, 0.0])
        ekf.update_position(target, sigma_position=0.1)

        assert np.linalg.norm(target - ekf.position) < np.linalg.norm(target - before)
        assert ekf.position[0] > 0.0

    def test_tight_measurement_dominates(self):
        ekf = _make_ekf(initial_position_sigma=10.0)
        ekf.update_position(np.array([2.0, -1.0, 0.5]), sigma_position=1e-4)
        np.testing.assert_allclose(ekf.position, [2.0, -1.0, 0.5], atol=1e-4)

    def test_update_shrinks_position_uncertainty(self):
        ekf = _make_ekf()
        for _ in range(100):
            ekf.propagate(np.array([0.0, 0.0, 9.81]), np.zeros(3), dt=0.01)
        sigma_before = ekf.position_sigma()
        ekf.update_position(ekf.position.copy(), sigma_position=0.05)
        assert ekf.position_sigma() < sigma_before

    def test_innovation_is_measurement_minus_prediction(self):
        ekf = _make_ekf()
        innovation, S = ekf.innovation(np.array([3.0, 4.0, 0.0]), sigma_position=2.0)
        np.testing.assert_allclose(innovation, [3.0, 4.0, 0.0])
        # S = P_pos + sigma^2 I; the sigma^2 = 4 term dominates the tiny prior.
        assert S[0, 0] == pytest.approx(4.0, abs=1e-3)
        assert S[0, 1] == pytest.approx(0.0, abs=1e-9)
