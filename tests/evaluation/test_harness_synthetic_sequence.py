import csv
import json
from types import SimpleNamespace

import numpy as np

import nav_benchmark.evaluation.harness as harness
from nav_benchmark.datasets.mvsec import POSE_DTYPE
from nav_benchmark.evaluation.harness import evaluate_run_directory, resolve_ground_truth_path
from nav_benchmark.evaluation.metrics import EvalConfig
from nav_benchmark.trajectory.export import export_project_csv
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


def _write_synthetic_ground_truth(sequence_dir):
    gt_dir = sequence_dir / "ground_truth"
    gt_dir.mkdir(parents=True)
    with open(gt_dir / "trajectory.csv", "w", newline="", encoding="utf-8") as f:
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
            [0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
            [2.0, 1.0, 1.0, 100.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 0.0, 1.0, 0.0],
            [3.0, 1.0, 1.0, 101.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 0.0, 0.0, 1.0],
        ]
        writer.writerows(rows)


def _estimate_trajectory():
    timestamps = np.array([0.0, 1.0, 2.0, 3.0])
    positions = np.array(
        [
            [0.0, 0.0, 100.0],
            [1.1, 0.0, 100.0],
            [1.0, 1.1, 100.0],
            [1.0, 1.0, 101.2],
        ]
    )
    orientations = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)
    return Trajectory(
        timestamps=timestamps,
        method="imu_only",
        positions=positions,
        orientations=orientations,
        velocities=np.zeros((4, 3)),
        confidence=np.ones(4),
        health=np.array([PoseHealth.OK, PoseHealth.OK, PoseHealth.DEGRADED, PoseHealth.LOST], dtype=object),
        latency_ms=np.array([1.0, 2.0, 3.0, 4.0]),
    )


def test_evaluate_run_directory_with_generated_synthetic_ground_truth(tmp_path):
    sequence_dir = tmp_path / "sequence"
    _write_synthetic_ground_truth(sequence_dir)

    run_dir = tmp_path / "runs" / "20260628_120000_imu_only_unit"
    run_dir.mkdir(parents=True)
    export_project_csv(_estimate_trajectory(), run_dir / "estimated_trajectory.csv")
    with open(run_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump({"input": str(sequence_dir), "method": "imu_only", "sequence": "unit"}, f)

    gt_path = resolve_ground_truth_path(run_dir)
    harness_result = evaluate_run_directory(
        run_dir,
        eval_config=EvalConfig(alignment_policy="none"),
        sequence="unit",
        write_plots=False,
    )

    assert gt_path == sequence_dir / "ground_truth" / "trajectory.csv"
    assert harness_result.ground_truth_path == gt_path
    assert harness_result.result.metrics.ate_rmse > 0.0
    assert harness_result.result.runtime.latency_mean_ms == 2.5
    assert harness_result.result.failures.failed_frame_count == 1
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "error_vs_time.csv").exists()
    assert (run_dir / "error_vs_distance.csv").exists()
    assert (run_dir / "ground_truth_aligned.csv").exists()

    with open(run_dir / "metrics.json", encoding="utf-8") as f:
        metrics = json.load(f)
    assert metrics["runtime"]["latency_mean_ms"] == 2.5
    assert metrics["failures"]["failed_frame_count"] == 1


def test_load_ground_truth_trajectory_converts_mvsec_poses(monkeypatch, tmp_path):
    poses = np.empty(2, dtype=POSE_DTYPE)
    poses["t"] = [0.0, 1.0]
    poses["x"] = [1.0, 2.0]
    poses["y"] = [3.0, 4.0]
    poses["z"] = [5.0, 6.0]
    poses["qx"] = [0.0, 0.0]
    poses["qy"] = [0.0, 0.0]
    poses["qz"] = [0.0, 0.0]
    poses["qw"] = [1.0, 1.0]
    monkeypatch.setattr(harness, "load_mvsec_sequence", lambda _path: SimpleNamespace(gt_poses=poses))

    trajectory = harness.load_ground_truth_trajectory(tmp_path / "sample.h5")

    assert trajectory.method == "ground_truth"
    np.testing.assert_allclose(trajectory.timestamps, [0.0, 1.0])
    np.testing.assert_allclose(trajectory.positions, [[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]])
    assert trajectory.health.tolist() == ["OK", "OK"]


def test_load_ground_truth_trajectory_rejects_mvsec_without_poses(monkeypatch, tmp_path):
    monkeypatch.setattr(harness, "load_mvsec_sequence", lambda _path: SimpleNamespace(gt_poses=None))

    with np.testing.assert_raises_regex(ValueError, "No ground-truth poses"):
        harness.load_ground_truth_trajectory(tmp_path / "empty.h5")
