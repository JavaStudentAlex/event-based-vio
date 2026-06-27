import csv
import tempfile
from pathlib import Path

import numpy as np

from nav_benchmark.trajectory.export import _fmt_opt, export_project_csv, export_tum
from nav_benchmark.trajectory.models import ExportMetadata, PoseHealth, Trajectory


def test_export_project_csv():
    timestamps = np.array([1.0, 2.0])
    positions = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]])
    health = np.array([PoseHealth.OK, PoseHealth.LOST])

    traj = Trajectory(
        timestamps=timestamps, method="test", positions=positions, orientations=orientations, health=health
    )

    metadata = ExportMetadata()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.csv"
        export_project_csv(traj, path, metadata)

        with open(path) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == [
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

            row1 = next(reader)
            assert row1[0] == "1.000000000"
            assert row1[1] == "test"
            assert row1[13] == "OK"

            row2 = next(reader)
            assert row2[0] == "2.000000000"
            assert row2[13] == "LOST"

        assert metadata.health_counts["OK"] == 1
        assert metadata.health_counts["LOST"] == 1


def test_export_tum():
    timestamps = np.array([1.0, 2.0, 3.0])
    positions = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]])
    health = np.array([PoseHealth.OK, PoseHealth.DEGRADED, PoseHealth.LOST])

    traj = Trajectory(
        timestamps=timestamps, method="test", positions=positions, orientations=orientations, health=health
    )

    metadata = ExportMetadata()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.tum"
        filtered_count = export_tum(traj, path, metadata)

        assert filtered_count == 1
        assert metadata.tum_filtered_rows == 1

        with open(path) as f:
            lines = f.readlines()
            assert len(lines) == 2

            parts1 = lines[0].strip().split()
            assert parts1[0] == "1.000000000"

            parts2 = lines[1].strip().split()
            assert parts2[0] == "2.000000000"


def test_export_project_csv_with_velocities_and_confidence():
    timestamps = np.array([1.0])
    positions = np.array([[1.0, 2.0, 3.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0]])
    velocities = np.array([[0.1, 0.2, 0.3]])
    confidence = np.array([0.9])
    latency_ms = np.array([10.0])

    traj = Trajectory(
        timestamps=timestamps,
        method="test",
        positions=positions,
        orientations=orientations,
        velocities=velocities,
        confidence=confidence,
        latency_ms=latency_ms,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.csv"
        export_project_csv(traj, path)

        with open(path) as f:
            reader = csv.reader(f)
            _ = next(reader)
            row = next(reader)

            assert row[9] == "0.100000000"
            assert row[10] == "0.200000000"
            assert row[11] == "0.300000000"
            assert row[12] == "0.900000000"
            assert row[14] == "10.000"


def test_fmt_opt_edge_cases():
    assert _fmt_opt(0.0, 2) == "0.00"
    assert _fmt_opt(None, 2) == ""
    assert _fmt_opt("", 2) == ""


def test_export_project_csv_edge_cases():
    timestamps = np.array([1.0])
    positions = np.array([[1.0, 2.0, 3.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0]])

    traj = Trajectory(
        timestamps=timestamps,
        method="test",
        positions=positions,
        orientations=orientations,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.csv"
        export_project_csv(traj, path)

        with open(path) as f:
            reader = csv.reader(f)
            _ = next(reader)
            row = next(reader)

            assert row[9] == ""
            assert row[10] == ""
            assert row[11] == ""
            assert row[12] == ""
            assert row[14] == ""


def test_export_tum_health_filter():
    timestamps = np.array([1.0, 2.0])
    positions = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]])
    health = np.array([PoseHealth.LOST, PoseHealth.INVALID])

    traj = Trajectory(
        timestamps=timestamps, method="test", positions=positions, orientations=orientations, health=health
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.tum"
        filtered_count = export_tum(traj, path)

        assert filtered_count == 2
        with open(path) as f:
            lines = f.readlines()
            assert len(lines) == 0


def test_export_tum_no_metadata():
    timestamps = np.array([1.0])
    positions = np.array([[1.0, 2.0, 3.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0]])
    health = np.array([PoseHealth.OK])

    traj = Trajectory(
        timestamps=timestamps, method="test", positions=positions, orientations=orientations, health=health
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.tum"
        filtered_count = export_tum(traj, path)

        assert filtered_count == 0
