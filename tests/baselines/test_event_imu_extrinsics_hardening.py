"""Regression tests for hardened Event+IMU extrinsics diagnostics."""

import numpy as np

from nav_benchmark.baselines.event_imu import EventImuBackend, EventImuConfig
from nav_benchmark.baselines.imu import ImuOnlyConfig
from nav_benchmark.datasets.mvsec import IMU_DTYPE, Calibration, LoadDiagnostics, MvsecSequence, SequenceMetadata


def _imu_at_rest(duration_sec: float = 2.0, rate_hz: float = 100.0) -> np.ndarray:
    count = int(duration_sec * rate_hz)
    imu = np.empty(count, dtype=IMU_DTYPE)
    imu["t"] = np.arange(count) / rate_hz
    imu["ax"] = 0.2
    imu["ay"] = 0.0
    imu["az"] = 9.81
    imu["gx"] = 0.0
    imu["gy"] = 0.0
    imu["gz"] = 0.0
    return imu


def _static_sequence(transform: np.ndarray | None = None) -> MvsecSequence:
    frame_count = 40
    frames = np.zeros((frame_count, 64, 64), dtype=np.uint8)
    timestamps = np.linspace(0.025, 1.975, frame_count)
    calibration = Calibration()
    if transform is not None:
        calibration.imu_cam_transform_available = True
        calibration.data["imu_cam_transform"] = transform

    return MvsecSequence(
        metadata=SequenceMetadata(source_path="unit", sequence_name="extrinsics_hardening"),
        diagnostics=LoadDiagnostics(),
        calibration=calibration,
        imu=_imu_at_rest(),
        event_frames=frames,
        event_frame_timestamps=timestamps,
    )


def test_reused_backend_clears_stale_extrinsics_rejected_reason() -> None:
    invalid_transform = np.eye(4)
    invalid_transform[0, 0] = 2.0
    backend = EventImuBackend()

    backend.run(_static_sequence(invalid_transform), config=EventImuConfig(imu_config=ImuOnlyConfig()))
    assert backend.diagnostics["extrinsics_rejected_reason"] == "degenerate_or_not_rotation"

    backend.run(_static_sequence(np.eye(4)), config=EventImuConfig(imu_config=ImuOnlyConfig()))

    assert backend.diagnostics["extrinsics_applied"] is True
    assert backend.diagnostics["extrinsics_source"] == "calibration"
    assert "extrinsics_rejected_reason" not in backend.diagnostics


def test_rejects_non_orthonormal_rotation_even_when_determinant_is_one() -> None:
    shear_transform = np.eye(4)
    shear_transform[:3, :3] = np.array(
        [
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    backend = EventImuBackend()

    backend.run(_static_sequence(shear_transform), config=EventImuConfig(imu_config=ImuOnlyConfig()))

    assert backend.diagnostics["extrinsics_applied"] is False
    assert backend.diagnostics["extrinsics_source"] == "identity_fallback"
    assert backend.diagnostics["extrinsics_rejected_reason"] == "degenerate_or_not_rotation"
