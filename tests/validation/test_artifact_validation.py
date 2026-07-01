import csv
import json

from nav_benchmark.validation import (
    check_cross_consistency,
    check_error_vs_distance_csv,
    check_error_vs_time_csv,
    check_failure_notes,
    check_metrics_json,
    check_plot_file,
    check_run_manifest,
    check_trajectory_csv,
    check_tum_file,
)


# 1. Trajectory CSV checks
def test_check_trajectory_csv_valid(tmp_path):
    path = tmp_path / "estimated_trajectory.csv"
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
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            [
                "1.0",
                "imu_only",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "OK",
                "10.0",
            ]
        )
    res = check_trajectory_csv(path)
    assert res.passed, res.message


def test_check_trajectory_csv_wrong_columns(tmp_path):
    path = tmp_path / "estimated_trajectory_wrong.csv"
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
    ]  # Missing latency_ms (only 14 columns)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            ["1.0", "imu_only", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "1.0", "0.0", "0.0", "0.0", "1.0", "OK"]
        )
    res = check_trajectory_csv(path)
    assert not res.passed
    assert "Header has fewer than 15 columns" in res.message


def test_check_trajectory_csv_empty_data(tmp_path):
    path = tmp_path / "estimated_trajectory_empty.csv"
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
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
    res = check_trajectory_csv(path)
    assert not res.passed
    assert "No data rows found" in res.message


# 2. TUM checks
def test_check_tum_valid(tmp_path):
    path = tmp_path / "estimated_trajectory_tum.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("1.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n")
    res = check_tum_file(path)
    assert res.passed, res.message


def test_check_tum_invalid_format(tmp_path):
    path = tmp_path / "estimated_trajectory_tum.txt"
    # Row doesn't have 8 elements
    with open(path, "w", encoding="utf-8") as f:
        f.write("1.0 0.0 0.0 0.0\n")
    res = check_tum_file(path)
    assert not res.passed
    assert "does not have 8 elements" in res.message


# 3. Manifest checks
def test_check_manifest_valid(tmp_path):
    path = tmp_path / "run_manifest.json"
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
        "health_counts": {"OK": 1, "DEGRADED": 0, "LOST": 0, "INVALID": 0},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    res = check_run_manifest(path)
    assert res.passed, res.message


def test_check_manifest_missing_keys(tmp_path):
    path = tmp_path / "run_manifest_missing.json"
    manifest = {
        "method": "imu_only",
        "dataset": "synthetic",
        # Missing other keys
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    res = check_run_manifest(path)
    assert not res.passed
    assert "Manifest missing key" in res.message


# 4. Failure Notes checks
def test_check_failure_notes_valid_clean(tmp_path):
    path = tmp_path / "failure_notes.md"
    content = (
        "# Run Failure Notes\n"
        "## Health Summary\n"
        "## Detected Degraded/Lost Intervals\n"
        "No degraded or lost intervals were detected during this run.\n"
    )
    path.write_text(content, encoding="utf-8")

    # Write a matching manifest with 0 failure counts
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
        "health_counts": {"OK": 1, "DEGRADED": 0, "LOST": 0, "INVALID": 0},
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    res = check_failure_notes(path)
    assert res.passed, res.message


def test_check_failure_notes_valid_degraded(tmp_path):
    path = tmp_path / "failure_notes.md"
    content = "# Run Failure Notes\n## Health Summary\n## Detected Degraded/Lost Intervals\n- [10.0, 15.0] DEGRADED\n"
    path.write_text(content, encoding="utf-8")

    # Write a matching manifest with non-zero failure counts
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
        "health_counts": {"OK": 1, "DEGRADED": 1, "LOST": 0, "INVALID": 0},
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    res = check_failure_notes(path)
    assert res.passed, res.message


def test_check_failure_notes_missing_header(tmp_path):
    path = tmp_path / "failure_notes_missing.md"
    content = (
        "# Run Failure Notes\n## Health Summary\n"
        # Missing ## Detected Degraded/Lost Intervals
    )
    path.write_text(content, encoding="utf-8")
    res = check_failure_notes(path)
    assert not res.passed
    assert "Missing '## Detected Degraded/Lost Intervals' section" in res.message


# 5. Metrics checks
def test_check_metrics_json_valid(tmp_path):
    path = tmp_path / "metrics.json"
    metrics_data = {
        "status": "success",
        "config": {},
        "metrics": {"ate_rmse": 0.2},
        "alignment": {},
        "diagnostics": {},
        "coverage": {"total_estimate_poses": 1},
        "drift_bins": [],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f)
    res = check_metrics_json(path)
    assert res.passed, res.message


def test_check_metrics_json_missing_keys(tmp_path):
    path = tmp_path / "metrics_missing.json"
    metrics_data = {
        "status": "success"
        # Missing other keys
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f)
    res = check_metrics_json(path)
    assert not res.passed
    assert "Metrics missing key" in res.message


# 6. Error CSV checks
def test_check_error_csvs_valid(tmp_path):
    evt_path = tmp_path / "error_vs_time.csv"
    evd_path = tmp_path / "error_vs_distance.csv"

    evt_header = [
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
    with open(evt_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(evt_header)
        writer.writerow(["1.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "OK", "0.0"])

    evd_header = ["cumulative_distance", "error_magnitude", "health", "association_residual", "bin_start", "bin_end"]
    with open(evd_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(evd_header)
        writer.writerow(["0.0", "0.0", "OK", "0.0", "0.0", "1.0"])

    res_evt = check_error_vs_time_csv(evt_path)
    res_evd = check_error_vs_distance_csv(evd_path)
    assert res_evt.passed, res_evt.message
    assert res_evd.passed, res_evd.message


def test_check_error_csvs_wrong_headers(tmp_path):
    evt_path = tmp_path / "error_vs_time.csv"
    evd_path = tmp_path / "error_vs_distance.csv"

    with open(evt_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wrong", "headers"])
    with open(evd_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wrong", "headers"])

    res_evt = check_error_vs_time_csv(evt_path)
    res_evd = check_error_vs_distance_csv(evd_path)
    assert not res_evt.passed
    assert not res_evd.passed


# 7. Plot checks
def test_check_plot_valid(tmp_path):
    path = tmp_path / "plot.png"
    # File larger than 100 bytes
    path.write_bytes(b"0" * 150)
    res = check_plot_file(path)
    assert res.passed, res.message


def test_check_plot_too_small(tmp_path):
    path = tmp_path / "plot.png"
    # File smaller or equal to 100 bytes (e.g. 10 bytes)
    path.write_bytes(b"0" * 10)
    res = check_plot_file(path)
    assert not res.passed
    assert "Plot file too small" in res.message


# 8. Cross-consistency checks
def test_check_cross_consistency_matching(tmp_path):
    # Setup matching files in tmp_path
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
    with open(traj_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            [
                "1.0",
                "imu_only",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "OK",
                "10.0",
            ]
        )
        writer.writerow(
            [
                "2.0",
                "imu_only",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "DEGRADED",
                "10.0",
            ]
        )

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
        "health_counts": {"OK": 1, "DEGRADED": 1, "LOST": 0, "INVALID": 0},
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    tum_path = tmp_path / "estimated_trajectory_tum.txt"
    with open(tum_path, "w", encoding="utf-8") as f:
        # TUM row count should equal OK + DEGRADED count = 2
        f.write("1.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n")
        f.write("2.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n")

    metrics_path = tmp_path / "metrics.json"
    metrics_data = {
        "status": "success",
        "config": {},
        "metrics": {"ate_rmse": 0.2},
        "alignment": {},
        "diagnostics": {},
        "coverage": {
            "total_estimate_poses": 2  # Matches 2 trajectory rows
        },
        "drift_bins": [],
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f)

    res = check_cross_consistency(tmp_path)
    assert res.passed, res.message


def test_check_cross_consistency_mismatch(tmp_path):
    # Setup mismatching health count in manifest vs CSV
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
    with open(traj_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(
            [
                "1.0",
                "imu_only",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "OK",
                "10.0",
            ]
        )

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
            "OK": 10,  # Mismatch (CSV has 1)
            "DEGRADED": 0,
            "LOST": 0,
            "INVALID": 0,
        },
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    res = check_cross_consistency(tmp_path)
    assert not res.passed
    assert "Health count mismatch for 'OK'" in res.message
