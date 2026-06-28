import json
from pathlib import Path
from unittest import mock

import pytest

from nav_benchmark.run import main


def _create_minimal_run_dir(run_dir: Path, include_eval: bool = False):
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. estimated_trajectory.csv
    csv_path = run_dir / "estimated_trajectory.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms\n")
        f.write("0.0,imu_only,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0,OK,5.0\n")
        f.write("1.0,imu_only,1.0,0.0,0.0,0.0,0.0,0.0,1.0,1.0,0.0,0.0,1.0,OK,5.0\n")

    # 2. estimated_trajectory_tum.txt
    tum_path = run_dir / "estimated_trajectory_tum.txt"
    with open(tum_path, "w", encoding="utf-8") as f:
        f.write("0.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n")
        f.write("1.0 1.0 0.0 0.0 0.0 0.0 0.0 1.0\n")

    # 3. run_manifest.json
    manifest_path = run_dir / "run_manifest.json"
    manifest_data = {
        "method": "imu_only",
        "dataset": "synthetic",
        "sequence": "test_seq",
        "config": {},
        "timestamp_policy": "sec",
        "gravity": [0.0, 0.0, 9.81],
        "frames": {"source": "imu", "target": "world"},
        "units": {"position": "m", "orientation": "quat"},
        "alignment": {"policy": "se3", "tolerance_sec": 0.1},
        "code_version": "0.1.0",
        "status": "success",
        "health_counts": {"OK": 2, "DEGRADED": 0, "LOST": 0, "INVALID": 0}
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    # 4. failure_notes.md
    notes_path = run_dir / "failure_notes.md"
    notes_path.write_text(
        "# Run Failure Notes\n"
        "## Health Summary\n"
        "- **OK**: 2\n"
        "- **DEGRADED**: 0\n"
        "- **LOST**: 0\n"
        "- **INVALID**: 0\n"
        "## Detected Degraded/Lost Intervals\n"
        "No degraded or lost intervals were detected.\n",
        encoding="utf-8"
    )

    # 5. run.log
    log_path = run_dir / "run.log"
    log_path.write_text("[START] imu_only\n[FINISHED]\n", encoding="utf-8")

    if include_eval:
        # metrics.json
        metrics_path = run_dir / "metrics.json"
        metrics_data = {
            "status": "success",
            "config": {},
            "metrics": {},
            "alignment": {},
            "diagnostics": {},
            "coverage": {"total_estimate_poses": 2},
            "drift_bins": []
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f)

        # error_vs_time.csv
        evt_path = run_dir / "error_vs_time.csv"
        with open(evt_path, "w", encoding="utf-8") as f:
            f.write("timestamp,est_x,est_y,est_z,gt_aligned_x,gt_aligned_y,gt_aligned_z,error_x,error_y,error_z,error_magnitude,health,association_residual\n")
            f.write("0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,OK,0.0\n")
            f.write("1.0,1.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,OK,0.0\n")

        # error_vs_distance.csv
        evd_path = run_dir / "error_vs_distance.csv"
        with open(evd_path, "w", encoding="utf-8") as f:
            f.write("cumulative_distance,error_magnitude,health,association_residual,bin_start,bin_end\n")
            f.write("0.0,0.0,OK,0.0,0.0,20.0\n")
            f.write("1.0,0.0,OK,0.0,0.0,20.0\n")

        # plot files
        (run_dir / "trajectory_plot.png").write_bytes(b"dummy plot data" * 10)
        (run_dir / "drift_plot.png").write_bytes(b"dummy plot data" * 10)


def test_validate_cli_help():
    """Verify validate --help runs and exits 0."""
    with mock.patch("sys.argv", ["nav_benchmark.run", "validate", "--help"]), pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 0


def test_validate_cli_missing_args():
    """Verify validate subcommand fails if neither --run-dir nor --latest is specified."""
    with mock.patch("sys.argv", ["nav_benchmark.run", "validate"]), pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 2


def test_validate_cli_run_only_skip_eval(tmp_path):
    """Verify validation passes for a run-only directory when using --skip-eval."""
    run_dir = tmp_path / "runs" / "test_run"
    _create_minimal_run_dir(run_dir, include_eval=False)

    test_args = [
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        str(run_dir),
        "--skip-eval",
    ]

    with mock.patch("sys.argv", test_args):
        # Should exit 0
        main()


def test_validate_cli_run_only_fails_without_skip_eval(tmp_path):
    """Verify validation fails for a run-only directory if --skip-eval is not specified."""
    run_dir = tmp_path / "runs" / "test_run"
    _create_minimal_run_dir(run_dir, include_eval=False)

    test_args = [
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        str(run_dir),
    ]

    with mock.patch("sys.argv", test_args), pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1


def test_validate_cli_full_with_eval(tmp_path):
    """Verify validation passes for a directory with both run and eval artifacts."""
    run_dir = tmp_path / "runs" / "test_run"
    _create_minimal_run_dir(run_dir, include_eval=True)

    test_args = [
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        str(run_dir),
    ]

    with mock.patch("sys.argv", test_args):
        # Should exit 0
        main()


def test_validate_cli_latest(tmp_path):
    """Verify validation works with --latest flag and filters."""
    output_root = tmp_path / "runs"
    output_root.mkdir(parents=True, exist_ok=True)

    # Create one directory
    run_dir = output_root / "20260628_120000_imu_only_test_seq"
    _create_minimal_run_dir(run_dir, include_eval=True)

    # Let's verify --latest discovers it and validates it successfully
    test_args = [
        "nav_benchmark.run",
        "validate",
        "--latest",
        "--output-root",
        str(output_root),
        "--method",
        "imu_only",
        "--sequence",
        "test_seq",
    ]

    with mock.patch("sys.argv", test_args):
        # Should exit 0
        main()
