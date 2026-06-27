import csv
import tempfile
from pathlib import Path

import numpy as np
import pytest

from nav_benchmark.trajectory.export import export_project_csv, export_tum
from nav_benchmark.trajectory.models import ExportMetadata, PoseHealth, Trajectory


def test_synthetic_end_to_end_export():
    """
    Synthetic end-to-end test verifying project CSV and TUM export
    including metadata tracking of health counts and filtered row statistics.
    """
    # Create synthetic trajectory data with all four health states
    timestamps = np.array([100.0, 100.1, 100.2, 100.3])
    positions = np.array([[1.0, 2.0, 3.0], [1.1, 2.1, 3.1], [1.2, 2.2, 3.2], [1.3, 2.3, 3.3]])
    orientations = np.array(
        [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.7071, 0.7071], [0.0, 0.0, 1.0, 0.0], [0.7071, 0.0, 0.0, 0.7071]]
    )
    velocities = np.array([[0.1, -0.1, 0.05], [0.2, -0.2, 0.06], [0.3, -0.3, 0.07], [0.4, -0.4, 0.08]])
    confidence = np.array([0.95, 0.80, 0.40, 0.00])
    health = np.array([PoseHealth.OK, PoseHealth.DEGRADED, PoseHealth.LOST, PoseHealth.INVALID])
    latency_ms = np.array([5.2, 12.4, 8.1, 15.0])

    traj = Trajectory(
        timestamps=timestamps,
        method="multimodal_vio",
        positions=positions,
        orientations=orientations,
        velocities=velocities,
        confidence=confidence,
        health=health,
        latency_ms=latency_ms,
    )

    metadata = ExportMetadata(association_tolerance_sec=0.01, source_frame="imu", target_frame="world")

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "synthetic_trajectory.csv"
        tum_path = Path(tmpdir) / "synthetic_trajectory.tum"

        # 1. Test Project CSV Export
        export_project_csv(traj, csv_path, metadata)

        # Assert CSV file exists and contains the expected content
        assert csv_path.exists()
        with open(csv_path, newline="") as f:
            reader = list(csv.reader(f))

            # Header check
            assert reader[0] == [
                "timestamp",
                "method",
                "x",
                "y",
                "z",
                "qx",
                "qy",
                "qz",
                "qw",
                "vx",
                "vy",
                "vz",
                "confidence",
                "health",
                "latency_ms",
            ]

            # Verify row shapes and health label preservation
            assert len(reader) == 5  # Header + 4 data rows

            # Check row 1 (OK)
            assert reader[1][0] == "100.000000000"
            assert reader[1][1] == "multimodal_vio"
            assert reader[1][2] == "1.000000000"
            assert reader[1][9] == "0.100000000"
            assert reader[1][12] == "0.950000000"
            assert reader[1][13] == "OK"
            assert reader[1][14] == "5.200"

            # Check row 2 (DEGRADED)
            assert reader[2][0] == "100.100000000"
            assert reader[2][13] == "DEGRADED"
            assert reader[2][14] == "12.400"

            # Check row 3 (LOST)
            assert reader[3][0] == "100.200000000"
            assert reader[3][13] == "LOST"

            # Check row 4 (INVALID)
            assert reader[4][0] == "100.300000000"
            assert reader[4][13] == "INVALID"

        # Verify metadata health counts are accumulated properly
        assert metadata.health_counts == {"OK": 1, "DEGRADED": 1, "LOST": 1, "INVALID": 1}

        # 2. Test TUM Export (which filters LOST and INVALID)
        filtered_count = export_tum(traj, tum_path, metadata)

        assert filtered_count == 2
        assert metadata.tum_filtered_rows == 2
        assert tum_path.exists()

        with open(tum_path) as f:
            lines = f.read().splitlines()
            # Only OK and DEGRADED should be present
            assert len(lines) == 2

            # Line 1: OK
            parts1 = lines[0].split()
            assert len(parts1) == 8
            assert parts1[0] == "100.000000000"
            assert parts1[1] == "1.000000000"
            assert parts1[2] == "2.000000000"
            assert parts1[3] == "3.000000000"
            assert parts1[4] == "0.000000000"
            assert parts1[5] == "0.000000000"
            assert parts1[6] == "0.000000000"
            assert parts1[7] == "1.000000000"

            # Line 2: DEGRADED
            parts2 = lines[1].split()
            assert len(parts2) == 8
            assert parts2[0] == "100.100000000"
            assert parts2[1] == "1.100000000"
            assert float(parts2[6]) == pytest.approx(0.7071, abs=1e-4)


def test_export_metadata_defaults():
    """
    Verify the fields and defaults of ExportMetadata dataclass.
    """
    meta = ExportMetadata()
    assert meta.timestamp_unit == "seconds"
    assert meta.association_policy == "nearest_neighbor"
    assert meta.association_tolerance_sec is None
    assert meta.source_frame == "imu"
    assert meta.target_frame == "world"
    assert meta.position_units == "meters"
    assert meta.orientation_format == "quaternion_xyzw"
    assert meta.health_counts == {}
    assert meta.tum_filtered_rows == 0


def test_export_empty_trajectory():
    """
    Verifies that exporting an empty trajectory behaves gracefully.
    """
    empty_arr = np.empty((0,))
    empty_pos = np.empty((0, 3))
    empty_ori = np.empty((0, 4))

    traj = Trajectory(timestamps=empty_arr, method="empty_method", positions=empty_pos, orientations=empty_ori)

    metadata = ExportMetadata()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "empty.csv"
        tum_path = Path(tmpdir) / "empty.tum"

        export_project_csv(traj, csv_path, metadata)
        assert csv_path.exists()
        with open(csv_path, newline="") as f:
            reader = list(csv.reader(f))
            assert len(reader) == 1  # Only header

        assert metadata.health_counts == {}

        filtered = export_tum(traj, tum_path, metadata)
        assert filtered == 0
        assert metadata.tum_filtered_rows == 0
        assert tum_path.exists()
        with open(tum_path) as f:
            lines = f.read().splitlines()
            assert len(lines) == 0
