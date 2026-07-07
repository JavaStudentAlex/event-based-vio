import math

from src.vio.imu_processor import IMUProcessor, IMUSample


def test_imu_processor_initialization():
    proc = IMUProcessor()
    assert proc.q == (0.0, 0.0, 0.0, 1.0)
    assert proc.t_last is None


def test_imu_processor_single_sample():
    proc = IMUProcessor()
    sample = IMUSample(t=10.0, ax=0.0, ay=0.0, az=9.81, gx=0.1, gy=0.2, gz=0.3)
    q = proc.step([sample])
    # The first sample only initializes t_last and does not integrate, returning identity
    assert q == (0.0, 0.0, 0.0, 1.0)
    assert proc.t_last == 10.0


def test_imu_processor_zero_rotation():
    proc = IMUProcessor()
    s1 = IMUSample(t=10.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.0)
    s2 = IMUSample(t=11.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.0)
    q = proc.step([s1, s2])
    assert q == (0.0, 0.0, 0.0, 1.0)


def test_imu_processor_integration():
    proc = IMUProcessor()
    # Let's rotate around Z axis: gz = 1.0 rad/s.
    # Total dt = 1.0s. Expected rotation is 1.0 radian around Z.
    s1 = IMUSample(t=10.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=1.0)
    s2 = IMUSample(t=11.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=1.0)

    q = proc.step([s1, s2])

    # Expected axis-angle integration:
    # gz = 1.0, gx = gy = 0.
    # axis normalization in IMUProcessor:
    # L1 norm = abs(gx) + abs(gy) + abs(gz) = 1.0
    # axis = (0, 0, 1.0 / (1e-12 + 1.0)) approx (0, 0, 1)
    # angle = 1.0 * 1.0 = 1.0 rad.
    # dq = _axis_angle_to_quat((0, 0, 1), 1.0) = (0, 0, sin(0.5), cos(0.5))
    # self.q started as (0,0,0,1), so self.q * dq = dq.
    expected_z = math.sin(0.5) * (1.0 / (1e-12 + 1.0))
    expected_w = math.cos(0.5)

    assert abs(q[0]) < 1e-6
    assert abs(q[1]) < 1e-6
    assert abs(q[2] - expected_z) < 1e-6
    assert abs(q[3] - expected_w) < 1e-6


def test_imu_processor_negative_dt_ignored():
    proc = IMUProcessor()
    s1 = IMUSample(t=10.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=1.0)
    s2 = IMUSample(t=9.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=1.0)
    q = proc.step([s1, s2])
    # Since t2 < t1, dt = max(0.0, 9.0 - 10.0) = 0.0. No rotation should occur.
    assert q == (0.0, 0.0, 0.0, 1.0)
