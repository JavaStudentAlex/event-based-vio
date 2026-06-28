import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from nav_benchmark.run import main


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
    with mock.patch("sys.argv", test_args):
        with mock.patch("time.strftime", return_value=first_run_dir.name.split("_imu_only")[0]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1

    # Now run with --resume (should append -r1)
    resume_args = test_args + ["--resume"]
    with mock.patch("sys.argv", resume_args):
        with mock.patch("time.strftime", return_value=first_run_dir.name.split("_imu_only")[0]):
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

    with mock.patch("sys.argv", test_args):
        with pytest.raises(SystemExit):
            main()
