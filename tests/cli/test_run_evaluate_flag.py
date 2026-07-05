"""One-command benchmark path: run --evaluate produces the full artifact set."""

import csv
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from nav_benchmark.run import main


def _write_input_sequence(root: Path) -> None:
    (root / "imu").mkdir(parents=True)
    (root / "ground_truth").mkdir(parents=True)

    with open(root / "imu" / "imu.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps"])
        for i in range(10):
            writer.writerow([float(i), 0.1 * i, 0.05 * i, -9.81 + 0.2 * i, 0.01, 0.02, 0.03])

    with open(root / "ground_truth" / "trajectory.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp_s", "x_m", "y_m", "z_m", "yaw_deg", "qx", "qy", "qz", "qw", "vx_mps", "vy_mps", "vz_mps"]
        )
        for i in range(10):
            writer.writerow([float(i), 0.3 * i, 0.2 * i, 100.0 + 0.1 * i, 0.0, 0.0, 0.0, 0.0, 1.0, 0.3, 0.2, 0.1])


def _cli(argv: list[str]) -> None:
    with mock.patch.object(sys, "argv", ["nav_benchmark.run", *argv]):
        main()


def test_run_with_evaluate_writes_full_artifact_set(tmp_path):
    input_dir = tmp_path / "input"
    _write_input_sequence(input_dir)
    output_root = tmp_path / "runs"

    _cli(
        [
            "run",
            "--method",
            "imu_only",
            "--dataset",
            "synthetic",
            "--sequence",
            "one_cmd",
            "--input",
            str(input_dir),
            "--output-root",
            str(output_root),
            "--evaluate",
        ]
    )

    run_dirs = list(output_root.glob("*_imu_only_one_cmd"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    for artifact in (
        "estimated_trajectory.csv",
        "estimated_trajectory_tum.txt",
        "run_manifest.json",
        "failure_notes.md",
        "run.log",
        "metrics.json",
        "ground_truth_aligned.csv",
        "error_vs_time.csv",
        "error_vs_distance.csv",
        "trajectory_plot.png",
        "drift_plot.png",
    ):
        assert (run_dir / artifact).exists(), f"missing {artifact}"

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["status"] == "OK"
    assert metrics["metrics"]["drift_percent"] is not None

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["evaluation"]["status"] == "success"

    log_text = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "Evaluating run against ground truth..." in log_text

    # The full validation (run + eval artifacts) must pass on the same directory.
    _cli(["validate", "--run-dir", str(run_dir)])


def test_run_with_evaluate_fails_without_ground_truth(tmp_path):
    output_root = tmp_path / "runs"

    with pytest.raises(SystemExit) as excinfo:
        _cli(
            [
                "run",
                "--method",
                "imu_only",
                "--dataset",
                "synthetic",
                "--sequence",
                "no_gt",
                "--output-root",
                str(output_root),
                "--evaluate",
            ]
        )
    assert excinfo.value.code == 1

    # Run artifacts still exist; evaluation failure is recorded, not hidden.
    run_dirs = list(output_root.glob("*_imu_only_no_gt"))
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "estimated_trajectory.csv").exists()
    metrics = json.loads((run_dirs[0] / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["status"] == "failed"
