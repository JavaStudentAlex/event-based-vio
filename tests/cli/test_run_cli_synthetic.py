import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from nav_benchmark.run import main


def _write_generated_sequence(root: Path) -> None:
    (root / "imu").mkdir(parents=True)
    (root / "ground_truth").mkdir(parents=True)

    with open(root / "imu" / "imu.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps"])
        for t in range(6):
            writer.writerow([float(t), 0.0, 0.0, -9.81, 0.0, 0.0, 0.0])

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
            [0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
            [2.0, 2.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
            [3.0, 2.0, 1.0, 100.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 0.0, 1.0, 0.0],
            [4.0, 2.0, 2.0, 100.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 0.0, 1.0, 0.0],
            [5.0, 2.0, 2.0, 101.0, 90.0, 0.0, 0.0, 0.70710678, 0.70710678, 0.0, 0.0, 1.0],
        ]
        writer.writerows(rows)


def test_cli_entrypoint_subprocess(tmp_path):
    """
    Test invoking the CLI as a subprocess to verify the run module entrypoint.
    """
    output_root = tmp_path / "runs"
    cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "test_seq_sub",
        "--output-root",
        str(output_root),
    ]

    # Ensure python path has src directory
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI execution failed with stdout:\n{res.stdout}\nstderr:\n{res.stderr}"

    # Verify run folder creation
    run_folders = list(output_root.glob("*_imu_only_test_seq_sub"))
    assert len(run_folders) == 1
    run_dir = run_folders[0]

    assert (run_dir / "estimated_trajectory.csv").exists()
    assert (run_dir / "estimated_trajectory_tum.txt").exists()
    assert (run_dir / "run.log").exists()

    # Check non-emptiness
    assert (run_dir / "estimated_trajectory.csv").stat().st_size > 0
    assert (run_dir / "estimated_trajectory_tum.txt").stat().st_size > 0
    assert (run_dir / "run.log").stat().st_size > 0

    # Check log contents
    log_content = (run_dir / "run.log").read_text()
    assert "[START]" in log_content
    assert "[FINISHED]" in log_content
    assert "Method: imu_only" in log_content
    assert "Dataset: synthetic" in log_content


def test_cli_run_and_eval_generated_synthetic_sequence(tmp_path):
    sequence_dir = tmp_path / "generated_sequence"
    _write_generated_sequence(sequence_dir)
    output_root = tmp_path / "runs"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    run_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "generated_seq",
        "--input",
        str(sequence_dir),
        "--output-root",
        str(output_root),
    ]
    run_res = subprocess.run(run_cmd, env=env, capture_output=True, text=True)
    assert run_res.returncode == 0, f"stdout: {run_res.stdout}\nstderr: {run_res.stderr}"

    run_dirs = list(output_root.glob("*_imu_only_generated_seq"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    with open(run_dir / "run_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["input"] == str(sequence_dir)
    assert manifest["config"]["gravity"] == [0.0, 0.0, -9.81]
    assert manifest["config"]["initial_position"] == [0.0, 0.0, 100.0]

    eval_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        str(run_dir),
        "--alignment-policy",
        "none",
    ]
    eval_res = subprocess.run(eval_cmd, env=env, capture_output=True, text=True)
    assert eval_res.returncode == 0, f"stdout: {eval_res.stdout}\nstderr: {eval_res.stderr}"

    with open(run_dir / "metrics.json", encoding="utf-8") as f:
        metrics = json.load(f)
    assert metrics["status"] == "OK"
    assert metrics["runtime"]["update_count"] == 6
    assert metrics["failures"]["failed_frame_count"] == 0


def test_cli_main_direct(tmp_path):
    """
    Test calling main directly with mocked sys.argv.
    Also tests --resume behavior.
    """
    output_root = tmp_path / "runs"
    test_args = [
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "test_seq_direct",
        "--output-root",
        str(output_root),
    ]

    # Run the first time
    with mock.patch("sys.argv", test_args):
        main()

    run_folders = list(output_root.glob("*_imu_only_test_seq_direct"))
    assert len(run_folders) == 1
    first_run_dir = run_folders[0]
    assert (first_run_dir / "estimated_trajectory.csv").exists()

    # Try running a second time with the exact same timestamp (mocked time.strftime)
    # Without --resume, it should exit with code 1
    with (
        mock.patch("sys.argv", test_args),
        mock.patch("time.strftime", return_value=first_run_dir.name.split("_imu_only")[0]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 1

    # Now run with --resume (should append -r1)
    resume_args = [*test_args, "--resume"]
    with (
        mock.patch("sys.argv", resume_args),
        mock.patch("time.strftime", return_value=first_run_dir.name.split("_imu_only")[0]),
    ):
        main()

    # Verify that -r1 directory exists and contains files
    resume_run_folders = list(output_root.glob("*_imu_only_test_seq_direct-r1"))
    assert len(resume_run_folders) == 1
    resume_dir = resume_run_folders[0]
    assert (resume_dir / "estimated_trajectory.csv").exists()
    assert (resume_dir / "estimated_trajectory_tum.txt").exists()
    assert (resume_dir / "run.log").exists()


def test_cli_missing_input_for_mvsec(tmp_path):
    """
    Test that --input is required if --dataset is mvsec.
    """
    output_root = tmp_path / "runs"
    test_args = [
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "mvsec",
        "--sequence",
        "outdoor_day1",
        "--output-root",
        str(output_root),
    ]

    with mock.patch("sys.argv", test_args), pytest.raises(SystemExit):
        main()
