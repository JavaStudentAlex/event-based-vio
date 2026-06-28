import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class ValidationResult:
    check_name: str
    passed: bool
    message: str


def check_trajectory_csv(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_trajectory_csv", False, f"File does not exist: {path}")

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return ValidationResult("check_trajectory_csv", False, "File is empty")

            expected_cols = [
                "timestamp", "method", "x", "y", "z",
                "qx", "qy", "qz", "qw",
                "vx", "vy", "vz",
                "confidence", "health", "latency_ms"
            ]
            if len(header) < 15:
                return ValidationResult("check_trajectory_csv", False, f"Header has fewer than 15 columns: {len(header)}")
            if header[:15] != expected_cols:
                return ValidationResult("check_trajectory_csv", False, f"Header mismatch. Expected first 15 columns to be {expected_cols}, got {header[:15]}")

            rows_count = 0
            for idx, row in enumerate(reader):
                if not row:
                    continue
                rows_count += 1
                if len(row) < 15:
                    return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} has length {len(row)} < 15")

                # Parse and verify columns
                try:
                    ts = float(row[0])
                    if not np.isfinite(ts):
                        return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} timestamp is non-finite")
                except ValueError:
                    return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} timestamp '{row[0]}' is not a float")

                # Positions
                for c in [2, 3, 4]:
                    try:
                        val = float(row[c])
                        if not np.isfinite(val):
                            return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} position col {c} is non-finite")
                    except ValueError:
                        return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} position col {c} '{row[c]}' is not a float")

                # Orientations
                for c in [5, 6, 7, 8]:
                    try:
                        val = float(row[c])
                        if not np.isfinite(val):
                            return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} orientation col {c} is non-finite")
                    except ValueError:
                        return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} orientation col {c} '{row[c]}' is not a float")

                # Velocities
                for c in [9, 10, 11]:
                    val = row[c]
                    if val != "":
                        try:
                            fval = float(val)
                            if not np.isfinite(fval):
                                return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} velocity col {c} is non-finite")
                        except ValueError:
                            return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} velocity col {c} '{val}' is not a float")

                # Confidence
                val = row[12]
                if val != "":
                    try:
                        fval = float(val)
                        if not np.isfinite(fval):
                            return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} confidence is non-finite")
                    except ValueError:
                        return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} confidence '{val}' is not a float")

                # Health
                health_val = row[13]
                if health_val not in ["OK", "DEGRADED", "LOST", "INVALID", ""]:
                    return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} health '{health_val}' is invalid")

                # Latency_ms
                val = row[14]
                if val != "":
                    try:
                        fval = float(val)
                        if not np.isfinite(fval):
                            return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} latency_ms is non-finite")
                    except ValueError:
                        return ValidationResult("check_trajectory_csv", False, f"Row {idx+2} latency_ms '{val}' is not a float")

            if rows_count == 0:
                return ValidationResult("check_trajectory_csv", False, "No data rows found")

            return ValidationResult("check_trajectory_csv", True, "Trajectory CSV is valid")
    except Exception as e:
        return ValidationResult("check_trajectory_csv", False, f"Failed to read CSV: {e}")


def check_tum_file(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_tum_file", False, f"TUM file does not exist: {path}")

    try:
        lines = []
        with open(path, encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) != 8:
                    return ValidationResult("check_tum_file", False, f"Row {idx+1} does not have 8 elements: {line}")
                try:
                    vals = [float(x) for x in parts]
                except ValueError as e:
                    return ValidationResult("check_tum_file", False, f"Row {idx+1} has non-numeric elements: {e}")
                lines.append(vals)
    except Exception as e:
        return ValidationResult("check_tum_file", False, f"Failed to read TUM file: {e}")

    if not lines:
        return ValidationResult("check_tum_file", False, "TUM file is empty")

    # Check companion CSV if it exists
    companion_csv = None
    if path.name.endswith("_tum.txt"):
        csv_name = path.name[:-8] + ".csv"
        companion_csv = path.parent / csv_name
    if companion_csv is None or not companion_csv.exists():
        companion_csv = path.parent / "estimated_trajectory.csv"

    if companion_csv.exists():
        health_map = {}
        try:
            with open(companion_csv, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                if "timestamp" in header and "health" in header:
                    ts_idx = header.index("timestamp")
                    health_idx = header.index("health")
                    for row in reader:
                        if not row:
                            continue
                        try:
                            ts_val = float(row[ts_idx])
                            h_val = row[health_idx]
                            health_map[ts_val] = h_val
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            return ValidationResult("check_tum_file", False, f"Failed to read companion CSV for cross check: {e}")

        # Verify no health == LOST or INVALID in matching timestamps
        for idx, row in enumerate(lines):
            ts = row[0]
            # Find nearest timestamp within 1e-4 seconds
            best_match = None
            min_diff = float("inf")
            for csv_ts in health_map:
                diff = abs(csv_ts - ts)
                if diff < min_diff:
                    min_diff = diff
                    best_match = csv_ts

            if min_diff < 1e-4 and best_match is not None:
                h_val = health_map[best_match]
                if h_val in ["LOST", "INVALID"]:
                    return ValidationResult(
                        "check_tum_file",
                        False,
                        f"TUM row {idx+1} at timestamp {ts} matches pose with health '{h_val}' in CSV"
                    )

    return ValidationResult("check_tum_file", True, "TUM file format is valid")


def check_run_manifest(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_run_manifest", False, f"File does not exist: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)

        required_keys = [
            "method", "dataset", "sequence", "config",
            "timestamp_policy", "gravity", "frames", "units",
            "alignment", "code_version", "status", "health_counts"
        ]
        for key in required_keys:
            if key not in manifest:
                return ValidationResult("check_run_manifest", False, f"Manifest missing key: '{key}'")

        hc = manifest.get("health_counts", {})
        for h in ["OK", "DEGRADED", "LOST", "INVALID"]:
            if h not in hc:
                return ValidationResult("check_run_manifest", False, f"health_counts missing key: '{h}'")

        return ValidationResult("check_run_manifest", True, "Run manifest is valid")
    except Exception as e:
        return ValidationResult("check_run_manifest", False, f"Failed to parse manifest: {e}")


def check_failure_notes(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_failure_notes", False, f"File does not exist: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        if "# Run Failure Notes" not in content:
            return ValidationResult("check_failure_notes", False, "Missing '# Run Failure Notes' header")
        if "## Health Summary" not in content:
            return ValidationResult("check_failure_notes", False, "Missing '## Health Summary' section")
        if "## Detected Degraded/Lost Intervals" not in content:
            return ValidationResult("check_failure_notes", False, "Missing '## Detected Degraded/Lost Intervals' section")

        # Try to find run_manifest.json to check if counts are zero
        manifest_path = path.parent / "run_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                hc = manifest.get("health_counts", {})
                degraded_lost_invalid_sum = sum(hc.get(h, 0) for h in ["DEGRADED", "LOST", "INVALID"])
                if degraded_lost_invalid_sum == 0:
                    if "No degraded or lost intervals were detected." not in content:
                        return ValidationResult(
                            "check_failure_notes",
                            False,
                            "Expected 'No degraded or lost intervals were detected.' because health counts show no failures"
                        )
            except Exception:
                pass

        return ValidationResult("check_failure_notes", True, "Failure notes file is valid")
    except Exception as e:
        return ValidationResult("check_failure_notes", False, f"Failed to read failure notes: {e}")


def check_metrics_json(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_metrics_json", False, f"File does not exist: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            metrics_data = json.load(f)

        required_keys = [
            "status", "config", "metrics", "alignment", "diagnostics", "coverage", "drift_bins"
        ]
        for key in required_keys:
            if key not in metrics_data:
                return ValidationResult("check_metrics_json", False, f"Metrics missing key: '{key}'")

        def check_val(val: Any) -> tuple[bool, str]:
            if isinstance(val, str):
                if val.lower() in ["nan", "inf", "-inf", "infinity", "-infinity"]:
                    return False, f"Found non-finite string representation '{val}'"
            elif isinstance(val, float):
                if not np.isfinite(val):
                    return False, f"Found non-finite float '{val}'"
            elif isinstance(val, dict):
                for k, v in val.items():
                    ok, msg = check_val(v)
                    if not ok:
                        return False, f"{k} -> {msg}"
            elif isinstance(val, list):
                for idx, v in enumerate(val):
                    ok, msg = check_val(v)
                    if not ok:
                        return False, f"[{idx}] -> {msg}"
            return True, ""

        ok, msg = check_val(metrics_data)
        if not ok:
            return ValidationResult("check_metrics_json", False, f"Non-finite value detected: {msg}")

        return ValidationResult("check_metrics_json", True, "Metrics JSON is valid")
    except Exception as e:
        return ValidationResult("check_metrics_json", False, f"Failed to parse metrics: {e}")


def check_error_vs_time_csv(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_error_vs_time_csv", False, f"File does not exist: {path}")

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return ValidationResult("check_error_vs_time_csv", False, "File is empty")

            expected_evt_header = [
                "timestamp", "est_x", "est_y", "est_z",
                "gt_aligned_x", "gt_aligned_y", "gt_aligned_z",
                "error_x", "error_y", "error_z", "error_magnitude",
                "health", "association_residual"
            ]
            expected_evt_header_alt = [
                "timestamp", "est_x", "est_y", "est_z",
                "gt_x", "gt_y", "gt_z",
                "err_x", "err_y", "err_z", "error_magnitude",
                "health", "assoc_residual_sec"
            ]
            if header != expected_evt_header and header != expected_evt_header_alt:
                return ValidationResult("check_error_vs_time_csv", False, f"Header mismatch. Got {header}")

            rows_count = 0
            for row in reader:
                if not row:
                    continue
                rows_count += 1
                if len(row) < len(header):
                    return ValidationResult("check_error_vs_time_csv", False, f"Row {rows_count+1} has length {len(row)} < {len(header)}")

            if rows_count == 0:
                return ValidationResult("check_error_vs_time_csv", False, "No data rows found")

            return ValidationResult("check_error_vs_time_csv", True, "Error vs Time CSV is valid")
    except Exception as e:
        return ValidationResult("check_error_vs_time_csv", False, f"Failed to read CSV: {e}")


def check_error_vs_distance_csv(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_error_vs_distance_csv", False, f"File does not exist: {path}")

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return ValidationResult("check_error_vs_distance_csv", False, "File is empty")

            expected_evd_header = [
                "cumulative_distance", "error_magnitude", "health",
                "association_residual", "bin_start", "bin_end"
            ]
            expected_evd_header_alt = [
                "cumulative_distance", "error_magnitude", "health",
                "assoc_residual_sec", "bin_start_m", "bin_end_m"
            ]
            if header != expected_evd_header and header != expected_evd_header_alt:
                return ValidationResult("check_error_vs_distance_csv", False, f"Header mismatch. Got {header}")

            rows_count = 0
            for row in reader:
                if not row:
                    continue
                rows_count += 1
                if len(row) < len(header):
                    return ValidationResult("check_error_vs_distance_csv", False, f"Row {rows_count+1} has length {len(row)} < {len(header)}")

            if rows_count == 0:
                return ValidationResult("check_error_vs_distance_csv", False, "No data rows found")

            return ValidationResult("check_error_vs_distance_csv", True, "Error vs Distance CSV is valid")
    except Exception as e:
        return ValidationResult("check_error_vs_distance_csv", False, f"Failed to read CSV: {e}")


def check_plot_file(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_plot_file", False, f"Plot file does not exist: {path}")

    try:
        size = path.stat().st_size
        if size <= 100:
            return ValidationResult("check_plot_file", False, f"Plot file too small: {size} bytes")
        return ValidationResult("check_plot_file", True, "Plot file exists and is valid")
    except Exception as e:
        return ValidationResult("check_plot_file", False, f"Failed to read plot file: {e}")


def check_run_log(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_run_log", False, f"run.log does not exist: {path}")

    try:
        size = path.stat().st_size
        if size == 0:
            return ValidationResult("check_run_log", False, "run.log is empty")
        return ValidationResult("check_run_log", True, "run.log exists and is non-empty")
    except Exception as e:
        return ValidationResult("check_run_log", False, f"Failed to check run.log: {e}")


def check_cross_consistency(run_dir: str | Path) -> ValidationResult:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    trajectory_path = run_dir / "estimated_trajectory.csv"
    tum_path = run_dir / "estimated_trajectory_tum.txt"
    metrics_path = run_dir / "metrics.json"

    if not trajectory_path.exists():
        return ValidationResult("check_cross_consistency", False, "Missing estimated_trajectory.csv for cross-consistency check")

    health_counts_csv = {"OK": 0, "DEGRADED": 0, "LOST": 0, "INVALID": 0}
    total_trajectory_rows = 0
    try:
        with open(trajectory_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            if "health" not in header:
                return ValidationResult("check_cross_consistency", False, "health column missing in trajectory CSV")
            health_idx = header.index("health")
            for row in reader:
                if not row:
                    continue
                total_trajectory_rows += 1
                h_val = row[health_idx]
                if not h_val:
                    h_val = "OK"
                health_counts_csv[h_val] = health_counts_csv.get(h_val, 0) + 1
    except Exception as e:
        return ValidationResult("check_cross_consistency", False, f"Failed to read trajectory CSV: {e}")

    # 1. Verify health_counts in manifest match actual health column distribution in trajectory CSV
    if manifest_path.exists():
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            manifest_health = manifest.get("health_counts", {})
            for h in ["OK", "DEGRADED", "LOST", "INVALID"]:
                m_count = manifest_health.get(h, 0)
                c_count = health_counts_csv.get(h, 0)
                if m_count != c_count:
                    return ValidationResult(
                        "check_cross_consistency",
                        False,
                        f"Health count mismatch for '{h}': manifest has {m_count}, CSV has {c_count}"
                    )
        except Exception as e:
            return ValidationResult("check_cross_consistency", False, f"Failed to check manifest consistency: {e}")

    # 2. Verify TUM row count equals OK+DEGRADED count from trajectory CSV
    if tum_path.exists():
        try:
            tum_row_count = 0
            with open(tum_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        tum_row_count += 1
            expected_tum_count = health_counts_csv["OK"] + health_counts_csv["DEGRADED"]
            if tum_row_count != expected_tum_count:
                return ValidationResult(
                    "check_cross_consistency",
                    False,
                    f"TUM row count {tum_row_count} does not match OK+DEGRADED count {expected_tum_count}"
                )
        except Exception as e:
            return ValidationResult("check_cross_consistency", False, f"Failed to check TUM consistency: {e}")

    # 3. Verify metrics.json coverage.total_estimate_poses matches trajectory CSV row count
    if metrics_path.exists():
        try:
            with open(metrics_path, encoding="utf-8") as f:
                metrics_data = json.load(f)

            coverage = metrics_data.get("coverage", {})
            total_est_poses = coverage.get("total_estimate_poses")

            if total_est_poses is None:
                failures = metrics_data.get("failures", {})
                if failures:
                    total_est_poses = sum(failures.get(k, 0) for k in ["ok_pose_count", "degraded_pose_count", "lost_pose_count", "invalid_pose_count"])
                else:
                    total_est_poses = metrics_data.get("runtime", {}).get("update_count")

            if total_est_poses != total_trajectory_rows:
                return ValidationResult(
                    "check_cross_consistency",
                    False,
                    f"metrics.json pose count {total_est_poses} does not match trajectory row count {total_trajectory_rows}"
                )
        except Exception as e:
            return ValidationResult("check_cross_consistency", False, f"Failed to check metrics consistency: {e}")

    return ValidationResult("check_cross_consistency", True, "All cross-consistency checks passed")


def validate_run_directory(run_dir: str | Path, expect_eval: bool = True) -> tuple[list[ValidationResult], bool]:
    run_dir = Path(run_dir)
    results = []

    # Baseline files (always expected)
    traj_csv = run_dir / "estimated_trajectory.csv"
    results.append(check_trajectory_csv(traj_csv))

    traj_tum = run_dir / "estimated_trajectory_tum.txt"
    results.append(check_tum_file(traj_tum))

    manifest = run_dir / "run_manifest.json"
    results.append(check_run_manifest(manifest))

    failure_notes = run_dir / "failure_notes.md"
    results.append(check_failure_notes(failure_notes))

    run_log = run_dir / "run.log"
    results.append(check_run_log(run_log))

    # Evaluation artifacts
    if expect_eval:
        metrics = run_dir / "metrics.json"
        results.append(check_metrics_json(metrics))

        evt_csv = run_dir / "error_vs_time.csv"
        results.append(check_error_vs_time_csv(evt_csv))

        evd_csv = run_dir / "error_vs_distance.csv"
        results.append(check_error_vs_distance_csv(evd_csv))

        # Find plots
        traj_plot = None
        for ext in [".png", ".svg"]:
            p = run_dir / f"trajectory_plot{ext}"
            if p.exists():
                traj_plot = p
                break
        if traj_plot is not None:
            results.append(check_plot_file(traj_plot))
        else:
            results.append(ValidationResult("check_plot_file", False, "Missing trajectory_plot.png or trajectory_plot.svg"))

        drift_plot = None
        for ext in [".png", ".svg"]:
            p = run_dir / f"drift_plot{ext}"
            if p.exists():
                drift_plot = p
                break
        if drift_plot is not None:
            results.append(check_plot_file(drift_plot))
        else:
            results.append(ValidationResult("check_plot_file", False, "Missing drift_plot.png or drift_plot.svg"))

    # Cross-consistency checks
    results.append(check_cross_consistency(run_dir))

    all_passed = all(r.passed for r in results)
    return results, all_passed
