import math

from src.vio.estimator import Estimator, EstimatorState
from src.vio.event_processor import EventPacket
from src.vio.imu_processor import IMUSample


def test_estimator_initialization():
    est = Estimator(width=640, height=480)
    assert est.t == 0.0
    assert est.events.width == 640
    assert est.events.height == 480


def test_estimator_step_empty():
    est = Estimator(width=640, height=480)
    state = est.step([], [])
    assert isinstance(state, EstimatorState)
    assert state.t == 0.0
    assert state.qx == 0.0
    assert state.qy == 0.0
    assert state.qz == 0.0
    assert state.qw == 1.0


def test_estimator_step_with_data():
    est = Estimator(width=100, height=100)

    # 1. First step: initialize IMU time
    pkt1 = EventPacket(t=1.0, x=[10], y=[20], p=[1])
    sample1 = IMUSample(t=1.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.0)
    state1 = est.step([pkt1], [sample1])

    # IMU first sample returns identity
    assert state1.t == 1.0
    assert state1.qx == 0.0
    assert state1.qy == 0.0
    assert state1.qz == 0.0
    assert state1.qw == 1.0

    # 2. Second step: perform rotation integration
    pkt2 = EventPacket(t=1.5, x=[15], y=[25], p=[0])
    # Rotate around Z axis by pi/2 rad/sec over 1.0 sec => pi/2 total rotation
    sample2 = IMUSample(t=2.0, ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=math.pi / 2.0)
    state2 = est.step([pkt2], [sample2])

    assert state2.t == 2.0
    # Expected rotation around Z axis:
    # angle = (pi/2) * dt = pi/2 * (2.0 - 1.0) = pi/2
    # sin(half_angle) = sin(pi/4) = sqrt(2)/2
    # cos(half_angle) = cos(pi/4) = sqrt(2)/2
    # qz should be ~sqrt(2)/2, qw should be ~sqrt(2)/2
    expected_val = math.sqrt(2.0) / 2.0
    assert math.isclose(state2.qz, expected_val, abs_tol=1e-5)
    assert math.isclose(state2.qw, expected_val, abs_tol=1e-5)
    assert math.isclose(state2.qx, 0.0, abs_tol=1e-5)
    assert math.isclose(state2.qy, 0.0, abs_tol=1e-5)
