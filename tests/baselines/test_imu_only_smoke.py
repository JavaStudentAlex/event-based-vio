import numpy as np
import pytest

from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.datasets.mvsec import (
    IMU_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
)
from nav_benchmark.trajectory.export import PROJECT_TRAJECTORY_COLUMNS
from nav_benchmark.trajectory.models import PoseHealth


def test_imu_only_smoke() -> None:
    # Create tiny synthetic IMU snippet: 10 steps at 100Hz
    # Constant slight angular velocity, zero acceleration (gravity removed below)
    N = 10
    imu_data = np.empty(N, dtype=IMU_DTYPE)
    imu_data["t"] = np.linspace(0.0, 0.09, N)
    imu_data["ax"] = np.zeros(N)
    imu_data["ay"] = np.zeros(N)
    imu_data["az"] = np.ones(N) * 9.81  # equal to gravity (no acceleration in world frame)
    imu_data["gx"] = np.zeros(N)
    imu_data["gy"] = np.zeros(N)
    imu_data["gz"] = np.ones(N) * 0.1  # constant yaw angular velocity

    metadata = SequenceMetadata(
        source_path="synthetic",
        sequence_name="unit_synthetic",
    )
    diagnostics = LoadDiagnostics()
    calibration = Calibration()

    sequence = MvsecSequence(
        metadata=metadata,
        diagnostics=diagnostics,
        calibration=calibration,
        imu=imu_data,
    )

    backend = ImuOnlyBackend()
    descriptor = backend.describe()
    assert descriptor.method == "imu_only"
    assert descriptor.required_streams == ("imu",)
    assert descriptor.output_columns == tuple(PROJECT_TRAJECTORY_COLUMNS)

    # Use standard gravity removal
    config = ImuOnlyConfig(
        gravity=np.array([0.0, 0.0, 9.81]),
        degraded_time_threshold=0.04,  # trigger degraded state early for testing
        lost_time_threshold=0.08,  # trigger lost state early for testing
    )

    result = backend.run_result(sequence, config=config)
    trajectory = result.trajectory
    assert result.config is config

    # Check method name
    assert trajectory.method == "imu_only"

    # Assert shape
    assert len(trajectory.timestamps) == N
    assert trajectory.positions.shape == (N, 3)
    assert trajectory.orientations.shape == (N, 4)
    if trajectory.velocities is not None:
        assert trajectory.velocities.shape == (N, 3)
    if trajectory.latency_ms is not None:
        assert len(trajectory.latency_ms) == N

    # Assert monotonic timestamps
    assert np.all(np.diff(trajectory.timestamps) > 0)

    # Assert health states are present and change appropriately based on config
    assert trajectory.health is not None
    assert len(trajectory.health) == N

    # The first pose should be OK
    assert trajectory.health[0] == PoseHealth.OK.value

    # Since time limits are set low:
    # dt_elapsed at index 5 is ~0.05s > degraded_time_threshold (0.04) -> should be DEGRADED or LOST
    # dt_elapsed at index 9 is ~0.09s > lost_time_threshold (0.08) -> should be LOST
    assert any(h == PoseHealth.DEGRADED.value for h in trajectory.health)
    assert any(h == PoseHealth.LOST.value for h in trajectory.health)


def test_imu_only_missing_imu() -> None:
    metadata = SequenceMetadata(
        source_path="synthetic",
        sequence_name="unit_synthetic",
    )
    sequence = MvsecSequence(
        metadata=metadata,
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(),
        imu=None,
    )
    backend = ImuOnlyBackend()
    with pytest.raises(ValueError, match="IMU data is missing or empty"):
        backend.run(sequence)
