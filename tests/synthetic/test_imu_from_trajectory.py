import numpy as np

from nav_benchmark.synthetic.config import ImuCfg
from nav_benchmark.synthetic.imu_from_trajectory import synthesize_imu

RATE = 200.0


def _straight():
    t = np.linspace(0.0, 2.0, 21)
    yaw = np.full(21, 90.0)
    vx = np.full(21, 10.0)
    vy = np.zeros(21)
    vz = np.zeros(21)
    return t, yaw, vx, vy, vz


def test_straight_trajectory_has_near_zero_yaw_rate():
    t, yaw, vx, vy, vz = _straight()
    imu = synthesize_imu(t, yaw, vx, vy, vz, ImuCfg(), add_noise=False)
    assert np.max(np.abs(imu.gz)) < 1e-6


def test_turning_trajectory_has_nonzero_gz():
    t = np.linspace(0.0, 2.0, 21)
    yaw = np.linspace(90.0, 150.0, 21)
    vr = np.radians(yaw)
    imu = synthesize_imu(t, yaw, 10 * np.sin(vr), 10 * np.cos(vr), np.zeros(21), ImuCfg(), add_noise=False)
    expected = np.radians(30.0)  # 60 deg over 2 s
    assert np.mean(imu.gz) > 0.0
    assert abs(float(np.mean(imu.gz)) - expected) < 1e-3


def test_timestamps_match_configured_rate():
    t, yaw, vx, vy, vz = _straight()
    imu = synthesize_imu(t, yaw, vx, vy, vz, ImuCfg(rate_hz=RATE), add_noise=False)
    dt = np.diff(imu.t)
    assert np.allclose(dt, 1.0 / RATE)


def test_gravity_and_no_nan():
    t, yaw, vx, vy, vz = _straight()
    imu = synthesize_imu(t, yaw, vx, vy, vz, ImuCfg(), add_noise=False)
    assert np.allclose(imu.az, -9.81, atol=1e-6)
    for arr in (imu.ax, imu.ay, imu.az, imu.gx, imu.gy, imu.gz):
        assert np.all(np.isfinite(arr))


def test_deterministic_noise_is_reproducible():
    t, yaw, vx, vy, vz = _straight()
    cfg = ImuCfg(deterministic_noise=True)
    a = synthesize_imu(t, yaw, vx, vy, vz, cfg, random_seed=11, add_noise=True)
    b = synthesize_imu(t, yaw, vx, vy, vz, cfg, random_seed=11, add_noise=True)
    assert np.array_equal(a.ax, b.ax)
    assert np.array_equal(a.gz, b.gz)
    # A different seed gives different noise.
    c = synthesize_imu(t, yaw, vx, vy, vz, cfg, random_seed=99, add_noise=True)
    assert not np.array_equal(a.ax, c.ax)
