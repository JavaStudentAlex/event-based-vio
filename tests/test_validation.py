import csv
import json

from nav_benchmark.validation import (
    check_cross_consistency,
    check_error_vs_distance_csv,
    check_error_vs_time_csv,
    check_failure_notes,
    check_metrics_json,
    check_plot_file,
    check_run_log,
    check_run_manifest,
    check_trajectory_csv,
    check_tum_file,
)


def test_check_trajectory_csv(tmp_path):
    path = tmp_path / "estimated_trajectory.csv"

    # Non-existent file
    res = check_trajectory_csv(path)
    assert not res.passed
    assert "File does not exist" in res.message

    # Empty file
    path.touch()
    res = check_trajectory_csv(path)
    assert not res.passed
    assert "File is empty" in res.message

    # Invalid header
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["col1", "col2"])
    res = check_trajectory_csv(path)
    assert not res.passed
    assert "Header has fewer than 15 columns" in res.message

    # Valid header but no rows
    cols = [
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
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
    res = check_trajectory_csv(path)
    assert not res.passed
    assert "No data rows found" in res.message

    # Valid file
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            [
                "1.0",
                "imu_only",
                "1.0",
                "2.0",
                "3.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.1",
                "0.2",
                "0.3",
                "0.99",
                "OK",
                "5.0",
            ]
        )
    res = check_trajectory_csv(path)
    assert res.passed
    assert "Trajectory CSV is valid" in res.message


def test_check_tum_file(tmp_path):
    path = tmp_path / "estimated_trajectory_tum.txt"

    # Non-existent file
    res = check_tum_file(path)
    assert not res.passed

    # Directory instead of file (raises Exception in _load_tum_lines)
    dir_path = tmp_path / "some_dir"
    dir_path.mkdir()
    res = check_tum_file(dir_path)
    assert not res.passed
    assert "Failed to read TUM file" in res.message

    # Malformed row (not 8 elements)
    with open(path, "w") as f:
        f.write("1.0 2.0 3.0\n")
    res = check_tum_file(path)
    assert not res.passed

    # Valid TUM
    with open(path, "w") as f:
        f.write("1.0 1.0 2.0 3.0 0.0 0.0 0.0 1.0\n")
    res = check_tum_file(path)
    assert res.passed

    # With companion CSV showing health LOST at matched timestamp
    csv_path = tmp_path / "estimated_trajectory.csv"
    cols = [
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
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            [
                "1.00001",
                "imu_only",
                "1.0",
                "2.0",
                "3.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.1",
                "0.2",
                "0.3",
                "0.99",
                "LOST",
                "5.0",
            ]
        )

    res = check_tum_file(path)
    assert not res.passed
    assert "matches pose with health 'LOST' in CSV" in res.message


def test_check_run_manifest(tmp_path):
    path = tmp_path / "run_manifest.json"

    # Missing file
    res = check_run_manifest(path)
    assert not res.passed

    # Missing keys
    with open(path, "w") as f:
        json.dump({"method": "imu_only"}, f)
    res = check_run_manifest(path)
    assert not res.passed
    assert "Manifest missing key" in res.message

    # Valid manifest
    manifest = {
        "method": "imu_only",
        "dataset": "synthetic",
        "sequence": "unit_synthetic",
        "config": {},
        "timestamp_policy": "seconds",
        "gravity": [0, 0, 9.81],
        "frames": {},
        "units": {},
        "alignment": {},
        "code_version": "v1.0",
        "status": "success",
        "health_counts": {"OK": 10, "DEGRADED": 0, "LOST": 0, "INVALID": 0},
    }
    with open(path, "w") as f:
        json.dump(manifest, f)
    res = check_run_manifest(path)
    assert res.passed


def test_check_failure_notes(tmp_path):
    path = tmp_path / "failure_notes.md"

    # Missing file
    res = check_failure_notes(path)
    assert not res.passed

    # Missing headers
    with open(path, "w") as f:
        f.write("# Run Failure Notes\n")
    res = check_failure_notes(path)
    assert not res.passed

    # Valid structure but no failures and missing exact phrase
    with open(path, "w") as f:
        f.write("# Run Failure Notes\n## Health Summary\n## Detected Degraded/Lost Intervals\n")
    # Also write manifest with zero failures
    manifest_path = tmp_path / "run_manifest.json"
    manifest = {
        "method": "imu_only",
        "dataset": "synthetic",
        "sequence": "unit_synthetic",
        "config": {},
        "timestamp_policy": "seconds",
        "gravity": [0, 0, 9.81],
        "frames": {},
        "units": {},
        "alignment": {},
        "code_version": "v1.0",
        "status": "success",
        "health_counts": {"OK": 10, "DEGRADED": 0, "LOST": 0, "INVALID": 0},
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)

    res = check_failure_notes(path)
    assert not res.passed
    assert "Expected 'No degraded or lost intervals were detected during this run.'" in res.message

    # Fully valid with zero failures
    with open(path, "w") as f:
        f.write(
            "# Run Failure Notes\n## Health Summary\n## Detected Degraded/Lost Intervals\nNo degraded or lost intervals were detected during this run.\n"
        )
    res = check_failure_notes(path)
    assert res.passed


def test_check_metrics_json(tmp_path):
    path = tmp_path / "metrics.json"

    # Missing file
    res = check_metrics_json(path)
    assert not res.passed

    # Missing keys
    with open(path, "w") as f:
        json.dump({"status": "OK"}, f)
    res = check_metrics_json(path)
    assert not res.passed

    # Non-finite value in dict
    metrics_data = {
        "status": "OK",
        "error_message": None,
        "config": {},
        "metrics": {"ate_rmse": "NaN"},
        "alignment": {},
        "diagnostics": {},
        "coverage": {},
        "drift_bins": [],
    }
    with open(path, "w") as f:
        json.dump(metrics_data, f)
    res = check_metrics_json(path)
    assert not res.passed
    assert "Non-finite value detected" in res.message

    # Fully valid
    metrics_data["metrics"]["ate_rmse"] = 0.55
    with open(path, "w") as f:
        json.dump(metrics_data, f)
    res = check_metrics_json(path)
    assert res.passed


def test_check_error_vs_time_csv(tmp_path):
    path = tmp_path / "error_vs_time.csv"

    # Missing
    res = check_error_vs_time_csv(path)
    assert not res.passed

    # Invalid header
    with open(path, "w") as f:
        f.write("col1,col2\n")
    res = check_error_vs_time_csv(path)
    assert not res.passed

    # Valid header with rows
    header = [
        "timestamp",
        "est_x",
        "est_y",
        "est_z",
        "gt_aligned_x",
        "gt_aligned_y",
        "gt_aligned_z",
        "error_x",
        "error_y",
        "error_z",
        "error_magnitude",
        "health",
        "association_residual",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(["1.0", "1", "2", "3", "1.1", "2.1", "3.1", "0.1", "0.1", "0.1", "0.173", "OK", "0.001"])
    res = check_error_vs_time_csv(path)
    assert res.passed


def test_check_error_vs_distance_csv(tmp_path):
    path = tmp_path / "error_vs_distance.csv"

    # Missing
    res = check_error_vs_distance_csv(path)
    assert not res.passed

    # Valid header and rows
    header = ["cumulative_distance", "error_magnitude", "health", "association_residual", "bin_start", "bin_end"]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(["10.0", "0.5", "OK", "0.001", "0.0", "20.0"])
    res = check_error_vs_distance_csv(path)
    assert res.passed


def test_check_plot_file(tmp_path):
    path = tmp_path / "plot.png"

    # Missing
    res = check_plot_file(path)
    assert not res.passed

    # Too small
    with open(path, "wb") as f:
        f.write(b"0" * 50)
    res = check_plot_file(path)
    assert not res.passed

    # Valid size
    with open(path, "wb") as f:
        f.write(b"0" * 150)
    res = check_plot_file(path)
    assert res.passed


def test_check_run_log(tmp_path):
    path = tmp_path / "run.log"

    # Missing
    res = check_run_log(path)
    assert not res.passed

    # Empty
    path.touch()
    res = check_run_log(path)
    assert not res.passed

    # Non-empty
    with open(path, "w") as f:
        f.write("Some logs\n")
    res = check_run_log(path)
    assert res.passed


def test_check_cross_consistency(tmp_path):
    # Setup files in tmp_path
    traj_path = tmp_path / "estimated_trajectory.csv"
    cols = [
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
    with open(traj_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            [
                "1.0",
                "imu_only",
                "1.0",
                "2.0",
                "3.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.1",
                "0.2",
                "0.3",
                "0.99",
                "OK",
                "5.0",
            ]
        )
        writer.writerow(
            [
                "2.0",
                "imu_only",
                "1.0",
                "2.0",
                "3.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.1",
                "0.2",
                "0.3",
                "0.99",
                "DEGRADED",
                "5.0",
            ]
        )

    # Missing manifest, tum, metrics -> should still pass on whatever is present
    res = check_cross_consistency(tmp_path)
    assert res.passed

    # Add manifest with mismatch
    manifest_path = tmp_path / "run_manifest.json"
    manifest = {
        "method": "imu_only",
        "dataset": "synthetic",
        "sequence": "unit_synthetic",
        "config": {},
        "timestamp_policy": "seconds",
        "gravity": [0, 0, 9.81],
        "frames": {},
        "units": {},
        "alignment": {},
        "code_version": "v1.0",
        "status": "success",
        "health_counts": {
            "OK": 2,
            "DEGRADED": 0,
            "LOST": 0,
            "INVALID": 0,
        },  # Mismatch: OK should be 1, DEGRADED should be 1
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
    res = check_cross_consistency(tmp_path)
    assert not res.passed
    assert "Health count mismatch for 'OK'" in res.message

    # Fix manifest health counts
    manifest["health_counts"] = {"OK": 1, "DEGRADED": 1, "LOST": 0, "INVALID": 0}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
    res = check_cross_consistency(tmp_path)
    assert res.passed

    # Add TUM file with correct row count (OK + DEGRADED = 2)
    tum_path = tmp_path / "estimated_trajectory_tum.txt"
    with open(tum_path, "w") as f:
        f.write("1.0 1.0 2.0 3.0 0.0 0.0 0.0 1.0\n2.0 1.0 2.0 3.0 0.0 0.0 0.0 1.0\n")
    res = check_cross_consistency(tmp_path)
    assert res.passed

    # TUM count mismatch
    with open(tum_path, "w") as f:
        f.write("1.0 1.0 2.0 3.0 0.0 0.0 0.0 1.0\n")
    res = check_cross_consistency(tmp_path)
    assert not res.passed
    assert "TUM row count 1 does not match OK+DEGRADED count 2" in res.message

    # Restore TUM
    with open(tum_path, "w") as f:
        f.write("1.0 1.0 2.0 3.0 0.0 0.0 0.0 1.0\n2.0 1.0 2.0 3.0 0.0 0.0 0.0 1.0\n")

    # Add metrics.json
    metrics_path = tmp_path / "metrics.json"
    metrics_data = {
        "status": "OK",
        "error_message": None,
        "config": {},
        "metrics": {"ate_rmse": 0.1},
        "alignment": {},
        "diagnostics": {},
        "coverage": {
            "total_estimate_poses": 3  # Mismatch: 3 vs 2
        },
        "drift_bins": [],
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics_data, f)
    res = check_cross_consistency(tmp_path)
    assert not res.passed
    assert "metrics.json pose count 3 does not match trajectory row count 2" in res.message

    # Fix metrics.json
    metrics_data["coverage"]["total_estimate_poses"] = 2
    with open(metrics_path, "w") as f:
        json.dump(metrics_data, f)
    res = check_cross_consistency(tmp_path)
    assert res.passed
