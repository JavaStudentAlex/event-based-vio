import csv

import numpy as np

from nav_benchmark.datasets.synthetic import (
    load_synthetic_sequence,
    read_synthetic_ground_truth_csv,
    read_synthetic_imu_csv,
)


def _write_generated_sequence(root):
    (root / "imu").mkdir(parents=True)
    (root / "ground_truth").mkdir(parents=True)

    with open(root / "imu" / "imu.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps"])
        for t in (0.0, 0.1, 0.2, 0.3):
            writer.writerow([t, 0.0, 0.0, -9.81, 0.0, 0.0, 0.0])

    with open(root / "ground_truth" / "trajectory.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp_s",
                "x_m",
                "y_m",
                "z_m",
                "yaw_deg",
                "qx",
                "qy",
                "qz",
                "qw",
                "vx_mps",
                "vy_mps",
                "vz_mps",
            ]
        )
        rows = [
            [0.0, 0.0, 0.0, 100.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 1.0, 0.0, 0.0],
            [0.1, 0.1, 0.0, 100.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 1.0, 0.0, 0.0],
            [0.2, 0.2, 0.1, 100.0, 45.0, 0.0, 0.0, 0.38268343, 0.92387953, 1.0, 1.0, 0.0],
            [0.3, 0.2, 0.2, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0],
        ]
        writer.writerows(rows)


def test_load_generated_synthetic_sequence(tmp_path):
    _write_generated_sequence(tmp_path)

    sequence = load_synthetic_sequence(tmp_path, sequence_name="unit_generated")

    assert sequence.metadata.sequence_name == "unit_generated"
    assert sequence.metadata.sample_counts == {"imu": 4, "gt_poses": 4}
    assert sequence.imu is not None
    assert sequence.gt_poses is not None
    np.testing.assert_allclose(sequence.imu["az"], [-9.81, -9.81, -9.81, -9.81])
    np.testing.assert_allclose(sequence.gt_poses["z"], [100.0, 100.0, 100.0, 100.0])


def test_read_generated_synthetic_ground_truth_csv(tmp_path):
    _write_generated_sequence(tmp_path)

    trajectory = read_synthetic_ground_truth_csv(tmp_path / "ground_truth" / "trajectory.csv")

    assert trajectory.method == "ground_truth"
    np.testing.assert_allclose(trajectory.timestamps, [0.0, 0.1, 0.2, 0.3])
    np.testing.assert_allclose(trajectory.velocities[2], [1.0, 1.0, 0.0])
    assert trajectory.health.tolist() == ["OK", "OK", "OK", "OK"]


def test_read_compact_task_ground_truth_csv(tmp_path):
    path = tmp_path / "trajectory.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "z", "qx", "qy", "qz", "qw", "vx", "vy", "vz", "confidence"])
        writer.writerow([0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0, 1.0, 10.0, 0.0, 0.0, 1.0])
        writer.writerow([0.033, 0.3, 0.0, 100.0, 0.0, 0.0, 0.001, 0.999, 10.0, 0.0, 0.0, 0.98])

    trajectory = read_synthetic_ground_truth_csv(path)

    np.testing.assert_allclose(trajectory.timestamps, [0.0, 0.033])
    np.testing.assert_allclose(trajectory.positions[:, 2], [100.0, 100.0])
    np.testing.assert_allclose(trajectory.confidence, [1.0, 0.98])


def test_read_synthetic_imu_csv(tmp_path):
    _write_generated_sequence(tmp_path)

    imu = read_synthetic_imu_csv(tmp_path / "imu" / "imu.csv")

    assert imu.dtype.names == ("t", "ax", "ay", "az", "gx", "gy", "gz")
    np.testing.assert_allclose(imu["t"], [0.0, 0.1, 0.2, 0.3])
