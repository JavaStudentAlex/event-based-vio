import csv
import json
import os
import subprocess
import sys
from pathlib import Path


def create_synthetic_trajectory_csv(path: Path, timestamps, x_offsets=0.0):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
        )
        for t in timestamps:
            # Let's create a circle or linear motion
            # x = cos(t), y = sin(t), z = t * 0.1
            import math

            x = math.cos(t) + x_offsets
            y = math.sin(t)
            z = t * 0.1
            writer.writerow([t, "imu_only", x, y, z, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, "OK", 5.0])


def test_eval_cli_success(tmp_path):
    """
    Test successful execution of eval CLI subcommand using synthetic inputs.
    """
    run_dir = tmp_path / "runs" / "test_run"
    run_dir.mkdir(parents=True)

    # 1. Create estimate trajectory
    est_path = run_dir / "estimated_trajectory.csv"
    timestamps = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    create_synthetic_trajectory_csv(est_path, timestamps, x_offsets=0.1)

    # 2. Create ground-truth trajectory
    gt_path = tmp_path / "gt_trajectory.csv"
    create_synthetic_trajectory_csv(gt_path, timestamps, x_offsets=0.0)

    # 3. Create run_manifest.json
    manifest_path = run_dir / "run_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(
            {
                "method": "imu_only",
                "dataset": "synthetic",
                "sequence": "test_seq",
                "input": str(gt_path),
                "config": {},
                "status": "success",
                "health_counts": {"OK": 6},
            },
            f,
        )

    # Execute eval subcommand with run_dir, resolving ground-truth from manifest
    cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        str(run_dir),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0 or "Evaluation completed successfully" not in res.stdout:
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
    assert res.returncode == 0, f"stdout: {res.stdout}\nstderr: {res.stderr}"
    assert "Evaluation completed successfully" in res.stdout

    # Verify generated artifacts
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "ground_truth_aligned.csv").exists()
    assert (run_dir / "error_vs_time.csv").exists()
    assert (run_dir / "error_vs_distance.csv").exists()
    assert (run_dir / "trajectory_plot.png").exists()
    assert (run_dir / "trajectory_plot.svg").exists()
    assert (run_dir / "drift_plot.png").exists()
    assert (run_dir / "drift_plot.svg").exists()

    # Read metrics.json and check keys
    with open(run_dir / "metrics.json") as f:
        metrics_data = json.load(f)
    assert metrics_data["status"] == "OK"
    assert "metrics" in metrics_data
    assert "alignment" in metrics_data
    assert "diagnostics" in metrics_data

    # Check updated run_manifest.json
    with open(manifest_path) as f:
        updated_manifest = json.load(f)
    if "evaluation" not in updated_manifest:
        print("MANIFEST:", updated_manifest)
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
    assert "evaluation" in updated_manifest
    assert updated_manifest["evaluation"]["status"] == "success"
    assert "metrics" in updated_manifest["evaluation"]


def test_eval_cli_latest_and_alignment(tmp_path):
    """
    Test using --latest flag and --alignment-policy none/se3.
    """
    output_root = tmp_path / "runs"
    run_dir = output_root / "20260628_120000_imu_only_test_seq"
    run_dir.mkdir(parents=True)

    # Create estimated_trajectory.csv
    est_path = run_dir / "estimated_trajectory.csv"
    timestamps = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    create_synthetic_trajectory_csv(est_path, timestamps, x_offsets=0.2)

    # Ground truth
    gt_path = tmp_path / "gt_trajectory.csv"
    create_synthetic_trajectory_csv(gt_path, timestamps, x_offsets=0.0)

    # Write run_manifest.json
    with open(run_dir / "run_manifest.json", "w") as f:
        json.dump(
            {
                "method": "imu_only",
                "dataset": "synthetic",
                "sequence": "test_seq",
                "input": str(gt_path),
                "status": "success",
            },
            f,
        )

    cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--latest",
        "--output-root",
        str(output_root),
        "--alignment-policy",
        "none",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"stdout: {res.stdout}\nstderr: {res.stderr}"

    # Verify metrics.json is written
    with open(run_dir / "metrics.json") as f:
        metrics_data = json.load(f)
    assert metrics_data["status"] == "OK"
    assert metrics_data["config"]["alignment_policy"] == "none"


def test_eval_cli_failure_cases(tmp_path):
    """
    Test eval CLI failure modes and diagnostic reporting.
    """
    run_dir = tmp_path / "runs" / "failed_run"
    run_dir.mkdir(parents=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    # Case 1: Missing estimated_trajectory.csv entirely
    cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        str(run_dir),
        "--ground-truth",
        "non_existent_gt.csv",
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Estimated trajectory not found" in res.stderr
    assert (run_dir / "metrics.json").exists()
    with open(run_dir / "metrics.json") as f:
        metrics_data = json.load(f)
    assert metrics_data["status"] == "failed"
    assert "Estimated trajectory not found" in metrics_data["error_message"]

    # Case 2: Missing ground truth file
    est_path = run_dir / "estimated_trajectory.csv"
    timestamps = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    create_synthetic_trajectory_csv(est_path, timestamps)

    cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        str(run_dir),
        "--ground-truth",
        "non_existent_gt.csv",
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Ground truth file not found" in res.stderr
    with open(run_dir / "metrics.json") as f:
        metrics_data = json.load(f)
    assert metrics_data["status"] == "failed"
    assert "Ground truth file not found" in metrics_data["error_message"]

    # Case 3: Insufficient timestamp overlap
    gt_path = tmp_path / "gt_far_away.csv"
    create_synthetic_trajectory_csv(gt_path, [200.0, 201.0, 202.0, 203.0, 204.0, 205.0])

    cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        str(run_dir),
        "--ground-truth",
        str(gt_path),
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Insufficient matched poses" in res.stderr or "synchronization failed" in res.stderr
    with open(run_dir / "metrics.json") as f:
        metrics_data = json.load(f)
    assert metrics_data["status"] == "failed"
