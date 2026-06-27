from pathlib import Path

import h5py
import numpy as np
import pytest

from nav_benchmark.datasets.mvsec import load_mvsec_sequence


@pytest.fixture
def synthetic_mvsec_h5(tmp_path: Path):
    h5_path = tmp_path / "synthetic_mvsec.h5"
    with h5py.File(h5_path, "w") as f:
        # events
        grp_events = f.create_group("/davis/left/events")
        grp_events.create_dataset("ts", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
        grp_events.create_dataset("x", data=np.array([10, 20, 30], dtype=np.uint16))
        grp_events.create_dataset("y", data=np.array([10, 20, 30], dtype=np.uint16))
        grp_events.create_dataset("p", data=np.array([1, 0, 1], dtype=np.int8))

        # imu
        grp_imu = f.create_group("/davis/left/imu")
        grp_imu.create_dataset("ts", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
        grp_imu.create_dataset("linear_acceleration_x", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
        grp_imu.create_dataset("linear_acceleration_y", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
        grp_imu.create_dataset("linear_acceleration_z", data=np.array([9.8, 9.8, 9.8], dtype=np.float64))
        grp_imu.create_dataset("angular_velocity_x", data=np.array([0.01, 0.02, 0.03], dtype=np.float64))
        grp_imu.create_dataset("angular_velocity_y", data=np.array([0.01, 0.02, 0.03], dtype=np.float64))
        grp_imu.create_dataset("angular_velocity_z", data=np.array([0.01, 0.02, 0.03], dtype=np.float64))

        # pose
        grp_pose = f.create_group("/davis/left/pose")
        grp_pose.create_dataset("ts", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
        grp_pose.create_dataset("px", data=np.array([0.0, 1.0, 2.0], dtype=np.float64))
        grp_pose.create_dataset("py", data=np.array([0.0, 1.0, 2.0], dtype=np.float64))
        grp_pose.create_dataset("pz", data=np.array([0.0, 1.0, 2.0], dtype=np.float64))
        grp_pose.create_dataset("qx", data=np.array([0.0, 0.0, 0.0], dtype=np.float64))
        grp_pose.create_dataset("qy", data=np.array([0.0, 0.0, 0.0], dtype=np.float64))
        grp_pose.create_dataset("qz", data=np.array([0.0, 0.0, 0.0], dtype=np.float64))
        grp_pose.create_dataset("qw", data=np.array([1.0, 1.0, 1.0], dtype=np.float64))

        # image_raw
        grp_img = f.create_group("/davis/left/image_raw")
        grp_img.create_dataset("ts", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
        grp_img.create_dataset("image_raw", data=np.zeros((3, 240, 346), dtype=np.uint8))

        # camera_info
        grp_cam = f.create_group("/davis/left/camera_info")
        grp_cam.create_dataset("K", data=np.eye(3, dtype=np.float64))
        grp_cam.create_dataset("D", data=np.zeros(5, dtype=np.float64))
        grp_cam.create_dataset("P", data=np.eye(3, 4, dtype=np.float64))

        # imu_cam_transform
        f.create_dataset("/davis/left/imu_cam_transform", data=np.eye(4, dtype=np.float64))

    return h5_path


def test_load_successful_sequence(synthetic_mvsec_h5: Path):
    seq = load_mvsec_sequence(synthetic_mvsec_h5)

    assert seq.metadata.sequence_name == "synthetic_mvsec"

    assert not seq.diagnostics.missing_streams
    assert not seq.diagnostics.malformed_streams
    assert not seq.diagnostics.layout_mismatch
    assert not seq.diagnostics.layout_errors

    assert seq.events is not None
    assert len(seq.events) == 3
    assert seq.events["t"][0] == 1.0

    assert seq.imu is not None
    assert len(seq.imu) == 3
    assert seq.imu["ax"][0] == 0.1

    assert seq.gt_poses is not None
    assert len(seq.gt_poses) == 3
    assert seq.gt_poses["x"][1] == 1.0

    assert seq.images is not None
    assert seq.images.shape == (3, 240, 346)

    assert seq.calibration.intrinsics_available
    assert seq.calibration.distortion_available
    assert seq.calibration.extrinsics_available
    assert seq.calibration.imu_cam_transform_available


def test_missing_stream(tmp_path: Path):
    h5_path = tmp_path / "missing_stream.h5"
    with h5py.File(h5_path, "w") as f:
        # only add events
        grp_events = f.create_group("/davis/left/events")
        grp_events.create_dataset("ts", data=np.array([1.0], dtype=np.float64))
        grp_events.create_dataset("x", data=np.array([10], dtype=np.uint16))
        grp_events.create_dataset("y", data=np.array([10], dtype=np.uint16))
        grp_events.create_dataset("p", data=np.array([1], dtype=np.int8))

    seq = load_mvsec_sequence(h5_path)
    assert seq.events is not None
    assert "imu" in seq.diagnostics.missing_streams
    assert "gt_poses" in seq.diagnostics.missing_streams
    assert "images" in seq.diagnostics.missing_streams
    assert not seq.diagnostics.layout_mismatch


def test_non_monotonic_timestamps(tmp_path: Path):
    h5_path = tmp_path / "non_monotonic.h5"
    with h5py.File(h5_path, "w") as f:
        grp_events = f.create_group("/davis/left/events")
        grp_events.create_dataset("ts", data=np.array([1.0, 3.0, 2.0], dtype=np.float64))
        grp_events.create_dataset("x", data=np.array([10, 20, 30], dtype=np.uint16))
        grp_events.create_dataset("y", data=np.array([10, 20, 30], dtype=np.uint16))
        grp_events.create_dataset("p", data=np.array([1, 0, 1], dtype=np.int8))

    seq = load_mvsec_sequence(h5_path)
    assert seq.events is None
    assert "events" in seq.diagnostics.malformed_streams
    assert any("not monotonic" in err for err in seq.diagnostics.layout_errors)


def test_duplicate_timestamps(tmp_path: Path):
    h5_path = tmp_path / "duplicate.h5"
    with h5py.File(h5_path, "w") as f:
        grp_events = f.create_group("/davis/left/events")
        grp_events.create_dataset("ts", data=np.array([1.0, 2.0, 2.0], dtype=np.float64))
        grp_events.create_dataset("x", data=np.array([10, 20, 30], dtype=np.uint16))
        grp_events.create_dataset("y", data=np.array([10, 20, 30], dtype=np.uint16))
        grp_events.create_dataset("p", data=np.array([1, 0, 1], dtype=np.int8))

    seq = load_mvsec_sequence(h5_path)
    assert seq.events is not None
    assert "events" not in seq.diagnostics.malformed_streams


def test_layout_mismatch(tmp_path: Path):
    h5_path = tmp_path / "layout_mismatch.h5"
    with h5py.File(h5_path, "w") as f:
        grp_events = f.create_group("/davis/left/events")
        # Missing 'p' and 'y'
        grp_events.create_dataset("ts", data=np.array([1.0], dtype=np.float64))
        grp_events.create_dataset("x", data=np.array([10], dtype=np.uint16))

    seq = load_mvsec_sequence(h5_path)
    assert seq.events is None
    assert seq.diagnostics.layout_mismatch
    assert "events" in seq.diagnostics.malformed_streams
    assert any("missing child dataset" in err for err in seq.diagnostics.layout_errors)


def test_missing_calibration(tmp_path: Path):
    h5_path = tmp_path / "missing_calib.h5"
    with h5py.File(h5_path, "w"):
        # no camera_info, no imu_cam_transform
        pass
    seq = load_mvsec_sequence(h5_path)
    assert not seq.calibration.intrinsics_available
    assert not seq.calibration.distortion_available
    assert not seq.calibration.extrinsics_available
    assert not seq.calibration.imu_cam_transform_available


def test_partial_calibration(tmp_path: Path):
    h5_path = tmp_path / "partial_calib.h5"
    with h5py.File(h5_path, "w") as f:
        grp_cam = f.create_group("/davis/left/camera_info")
        grp_cam.create_dataset("K", data=np.eye(3, dtype=np.float64))
        # No D or P
    seq = load_mvsec_sequence(h5_path)
    assert seq.calibration.intrinsics_available
    assert not seq.calibration.distortion_available
    assert not seq.calibration.extrinsics_available
    assert not seq.calibration.imu_cam_transform_available


def test_missing_images_and_poses(tmp_path: Path):
    h5_path = tmp_path / "missing_images_poses.h5"
    with h5py.File(h5_path, "w"):
        pass
    seq = load_mvsec_sequence(h5_path)
    assert seq.images is None
    assert seq.gt_poses is None
