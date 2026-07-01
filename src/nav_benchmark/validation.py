import csv
import json
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class ValidationResult:
    check_name: str
    passed: bool
    message: str


def _check_float_val(val: str, row_num: int, label: str, optional: bool = False) -> str | None:
    if optional and val == "":
        return None
    return _required_float_error(val, row_num, label)


def _required_float_error(val: str, row_num: int, label: str) -> str | None:
    try:
        if not np.isfinite(float(val)):
            return f"Row {row_num} {label} is non-finite"
    except ValueError:
        return f"Row {row_num} {label} '{val}' is not a float"
    return None


def _check_trajectory_header(header: list[str]) -> str | None:
    expected_cols = [
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
    if len(header) < 15:
        return f"Header has fewer than 15 columns: {len(header)}"
    if header[:15] != expected_cols:
        return f"Header mismatch. Expected first 15 columns to be {expected_cols}, got {header[:15]}"
    return None


def _validate_trajectory_row(row: list[str], row_num: int) -> str | None:
    if len(row) < 15:
        return f"Row {row_num} has length {len(row)} < 15"

    checks = [
        (0, "timestamp", False),
        (2, "position col 2", False),
        (3, "position col 3", False),
        (4, "position col 4", False),
        (5, "orientation col 5", False),
        (6, "orientation col 6", False),
        (7, "orientation col 7", False),
        (8, "orientation col 8", False),
        (9, "velocity col 9", True),
        (10, "velocity col 10", True),
        (11, "velocity col 11", True),
        (12, "confidence", True),
    ]

    for col, label, optional in checks:
        err = _check_float_val(row[col], row_num, label, optional)
        if err:
            return err

    if row[13] not in ("OK", "DEGRADED", "LOST", "INVALID", ""):
        return f"Row {row_num} health '{row[13]}' is invalid"

    return _check_float_val(row[14], row_num, "latency_ms", optional=True)


def _trajectory_csv_rows_error(reader: Iterator[list[str]]) -> str | None:
    rows_count = 0
    for idx, row in enumerate(reader):
        if not row:
            continue
        rows_count += 1
        err = _validate_trajectory_row(row, idx + 2)
        if err:
            return err
    return None if rows_count > 0 else "No data rows found"


def _trajectory_csv_error(path: Path) -> str | None:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return "File is empty"

        return _check_trajectory_header(header) or _trajectory_csv_rows_error(reader)


def check_trajectory_csv(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_trajectory_csv", False, f"File does not exist: {path}")

    try:
        err = _trajectory_csv_error(path)
    except Exception as e:
        return ValidationResult("check_trajectory_csv", False, f"Failed to read CSV: {e}")
    if err:
        return ValidationResult("check_trajectory_csv", False, err)
    return ValidationResult("check_trajectory_csv", True, "Trajectory CSV is valid")


def _parse_tum_line(line: str, row_num: int) -> tuple[list[float] | None, str | None]:
    parts = line.split()
    if len(parts) != 8:
        return None, f"Row {row_num} does not have 8 elements: {line}"
    try:
        return [float(x) for x in parts], None
    except ValueError as e:
        return None, f"Row {row_num} has non-numeric elements: {e}"


def _parse_all_tum_lines(f: Iterator[str]) -> tuple[list[list[float]], str | None]:
    lines: list[list[float]] = []
    for idx, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        vals, err = _parse_tum_line(line, idx + 1)
        if vals is None:
            return [], err or "Failed to parse line"
        lines.append(vals)
    return lines, None


def _load_tum_lines(path: Path) -> tuple[list[list[float]], str | None]:
    try:
        with open(path, encoding="utf-8") as f:
            return _parse_all_tum_lines(f)
    except Exception as e:
        return [], f"Failed to read TUM file: {e}"


def _get_companion_csv(path: Path) -> Path:
    if path.name.endswith("_tum.txt"):
        csv_name = path.name[:-8] + ".csv"
        companion = path.parent / csv_name
        if companion.exists():
            return companion
    return path.parent / "estimated_trajectory.csv"


def _health_column_indices(header: list[str]) -> tuple[int, int] | None:
    if "timestamp" in header and "health" in header:
        return header.index("timestamp"), header.index("health")
    return None


def _add_health_map_row(health_map: dict[float, str], row: list[str], ts_idx: int, health_idx: int) -> None:
    with suppress(ValueError, IndexError):
        health_map[float(row[ts_idx])] = row[health_idx]


def _load_health_map(csv_path: Path) -> tuple[dict[float, str], str | None]:
    health_map: dict[float, str] = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            indices = _health_column_indices(header)
            if indices is None:
                return health_map, None
            ts_idx, health_idx = indices
            for row in reader:
                if row:
                    _add_health_map_row(health_map, row, ts_idx, health_idx)
    except Exception as e:
        return {}, f"Failed to read companion CSV for cross check: {e}"
    return health_map, None


def _nearest_health_timestamp(ts: float, health_map: dict[float, str]) -> tuple[float | None, float]:
    best_match = None
    min_diff = float("inf")
    for csv_ts in health_map:
        diff = abs(csv_ts - ts)
        if diff < min_diff:
            min_diff = diff
            best_match = csv_ts
    return best_match, min_diff


def _tum_health_row_error(row: list[float], row_number: int, health_map: dict[float, str]) -> str | None:
    ts = row[0]
    best_match, min_diff = _nearest_health_timestamp(ts, health_map)
    if best_match is None:
        return None
    if min_diff >= 1e-4:
        return None
    h_val = health_map[best_match]
    if h_val in ["LOST", "INVALID"]:
        return f"TUM row {row_number} at timestamp {ts} matches pose with health '{h_val}' in CSV"
    return None


def _cross_check_tum_health(lines: list[list[float]], health_map: dict[float, str]) -> str | None:
    for idx, row in enumerate(lines):
        err = _tum_health_row_error(row, idx + 1, health_map)
        if err:
            return err
    return None


def _tum_companion_health_error(path: Path, lines: list[list[float]]) -> str | None:
    companion_csv = _get_companion_csv(path)
    if not companion_csv.exists():
        return None
    health_map, err = _load_health_map(companion_csv)
    if err:
        return err
    return _cross_check_tum_health(lines, health_map)


def check_tum_file(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_tum_file", False, f"TUM file does not exist: {path}")

    lines, err = _load_tum_lines(path)
    if err:
        return ValidationResult("check_tum_file", False, err)
    if not lines:
        return ValidationResult("check_tum_file", False, "TUM file is empty")

    err = _tum_companion_health_error(path, lines)
    if err:
        return ValidationResult("check_tum_file", False, err)

    return ValidationResult("check_tum_file", True, "TUM file format is valid")


def check_run_manifest(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_run_manifest", False, f"File does not exist: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)

        err = _manifest_required_key_error(manifest)
        if err:
            return ValidationResult("check_run_manifest", False, err)

        return ValidationResult("check_run_manifest", True, "Run manifest is valid")
    except Exception as e:
        return ValidationResult("check_run_manifest", False, f"Failed to parse manifest: {e}")


def _manifest_required_key_error(manifest: dict[str, Any]) -> str | None:
    required_keys = [
        "method",
        "dataset",
        "sequence",
        "config",
        "timestamp_policy",
        "gravity",
        "frames",
        "units",
        "alignment",
        "code_version",
        "status",
        "health_counts",
    ]
    for key in required_keys:
        if key not in manifest:
            return f"Manifest missing key: '{key}'"

    hc = manifest.get("health_counts", {})
    for health in ["OK", "DEGRADED", "LOST", "INVALID"]:
        if health not in hc:
            return f"health_counts missing key: '{health}'"
    return None


def _failure_notes_section_error(content: str) -> str | None:
    if "# Run Failure Notes" not in content:
        return "Missing '# Run Failure Notes' header"
    if "## Health Summary" not in content:
        return "Missing '## Health Summary' section"
    if "## Detected Degraded/Lost Intervals" not in content:
        return "Missing '## Detected Degraded/Lost Intervals' section"
    return None


def _failure_count_from_manifest(manifest_path: Path) -> int | None:
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        hc = manifest.get("health_counts", {})
        return int(hc.get("DEGRADED", 0)) + int(hc.get("LOST", 0)) + int(hc.get("INVALID", 0))
    except Exception:
        return None


def _failure_notes_manifest_error(path: Path, content: str) -> str | None:
    manifest_path = path.parent / "run_manifest.json"
    failure_count = _failure_count_from_manifest(manifest_path)
    if failure_count is None:
        return None
    if failure_count == 0 and "No degraded or lost intervals were detected during this run." not in content:
        return "Expected 'No degraded or lost intervals were detected during this run.' because health counts show no failures"
    return None


def check_failure_notes(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_failure_notes", False, f"File does not exist: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        err = _failure_notes_section_error(content) or _failure_notes_manifest_error(path, content)
        if err:
            return ValidationResult("check_failure_notes", False, err)
        return ValidationResult("check_failure_notes", True, "Failure notes file is valid")
    except Exception as e:
        return ValidationResult("check_failure_notes", False, f"Failed to read failure notes: {e}")


def _validate_finite_scalar(val: Any) -> tuple[bool, str]:
    if isinstance(val, str) and val.lower() in ["nan", "inf", "-inf", "infinity", "-infinity"]:
        return False, f"Found non-finite string representation '{val}'"
    if isinstance(val, float) and not np.isfinite(val):
        return False, f"Found non-finite float '{val}'"
    return True, ""


def _validate_finite_value(val: Any) -> tuple[bool, str]:
    if isinstance(val, dict):
        return _validate_finite_dict(val)
    if isinstance(val, list):
        return _validate_finite_list(val)
    return _validate_finite_scalar(val)


def _validate_finite_dict(values: dict) -> tuple[bool, str]:
    for key, value in values.items():
        ok, msg = _validate_finite_value(value)
        if not ok:
            return False, f"{key} -> {msg}"
    return True, ""


def _validate_finite_list(values: list) -> tuple[bool, str]:
    for idx, value in enumerate(values):
        ok, msg = _validate_finite_value(value)
        if not ok:
            return False, f"[{idx}] -> {msg}"
    return True, ""


def _metrics_required_key_error(metrics_data: dict[str, Any]) -> str | None:
    required_keys = ["status", "config", "metrics", "alignment", "diagnostics", "coverage", "drift_bins"]
    for key in required_keys:
        if key not in metrics_data:
            return f"Metrics missing key: '{key}'"
    return None


def _metrics_finite_value_error(metrics_data: dict[str, Any]) -> str | None:
    ok, msg = _validate_finite_value(metrics_data)
    if not ok:
        return f"Non-finite value detected: {msg}"
    return None


def check_metrics_json(path: str | Path) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult("check_metrics_json", False, f"File does not exist: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            metrics_data = json.load(f)
    except Exception as e:
        return ValidationResult("check_metrics_json", False, f"Failed to parse metrics: {e}")
    err = _metrics_required_key_error(metrics_data) or _metrics_finite_value_error(metrics_data)
    if err:
        return ValidationResult("check_metrics_json", False, err)
    return ValidationResult("check_metrics_json", True, "Metrics JSON is valid")


_ERROR_VS_TIME_HEADERS = (
    [
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
    ],
    [
        "timestamp",
        "est_x",
        "est_y",
        "est_z",
        "gt_x",
        "gt_y",
        "gt_z",
        "err_x",
        "err_y",
        "err_z",
        "error_magnitude",
        "health",
        "assoc_residual_sec",
    ],
)

_ERROR_VS_DISTANCE_HEADERS = (
    [
        "cumulative_distance",
        "error_magnitude",
        "health",
        "association_residual",
        "bin_start",
        "bin_end",
    ],
    [
        "cumulative_distance",
        "error_magnitude",
        "health",
        "assoc_residual_sec",
        "bin_start_m",
        "bin_end_m",
    ],
)


def _csv_header(reader: Iterator[list[str]], check_name: str) -> tuple[list[str] | None, ValidationResult | None]:
    try:
        return next(reader), None
    except StopIteration:
        return None, ValidationResult(check_name, False, "File is empty")


def _nonempty_rows_error(reader: Iterator[list[str]], header_len: int) -> str | None:
    rows_count = 0
    for row in reader:
        if not row:
            continue
        rows_count += 1
        if len(row) < header_len:
            return f"Row {rows_count + 1} has length {len(row)} < {header_len}"
    return None if rows_count > 0 else "No data rows found"


def _error_csv_content_result(
    path: Path,
    check_name: str,
    valid_headers: tuple[list[str], list[str]],
    success_message: str,
) -> ValidationResult:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header, result = _csv_header(reader, check_name)
        if result is not None:
            return result
        if header not in valid_headers:
            return ValidationResult(check_name, False, f"Header mismatch. Got {header}")
        err = _nonempty_rows_error(reader, len(header))
        if err:
            return ValidationResult(check_name, False, err)
        return ValidationResult(check_name, True, success_message)


def _check_error_csv(
    path: str | Path,
    check_name: str,
    valid_headers: tuple[list[str], list[str]],
    success_message: str,
) -> ValidationResult:
    path = Path(path)
    if not path.exists():
        return ValidationResult(check_name, False, f"File does not exist: {path}")

    try:
        return _error_csv_content_result(path, check_name, valid_headers, success_message)
    except Exception as e:
        return ValidationResult(check_name, False, f"Failed to read CSV: {e}")


def check_error_vs_time_csv(path: str | Path) -> ValidationResult:
    return _check_error_csv(
        path,
        "check_error_vs_time_csv",
        _ERROR_VS_TIME_HEADERS,
        "Error vs Time CSV is valid",
    )


def check_error_vs_distance_csv(path: str | Path) -> ValidationResult:
    return _check_error_csv(
        path,
        "check_error_vs_distance_csv",
        _ERROR_VS_DISTANCE_HEADERS,
        "Error vs Distance CSV is valid",
    )


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


def _empty_health_counts() -> dict[str, int]:
    return {"OK": 0, "DEGRADED": 0, "LOST": 0, "INVALID": 0}


def _add_trajectory_health_row(health_counts: dict[str, int], row: list[str], health_idx: int) -> int:
    if not row:
        return 0
    h_val = row[health_idx] or "OK"
    health_counts[h_val] = health_counts.get(h_val, 0) + 1
    return 1


def _load_trajectory_health(path: Path) -> tuple[dict[str, int], int, str | None]:
    health_counts = _empty_health_counts()
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            if "health" not in header:
                return {}, 0, "health column missing in trajectory CSV"
            health_idx = header.index("health")
            total_rows = sum(_add_trajectory_health_row(health_counts, row, health_idx) for row in reader)
    except Exception as e:
        return {}, 0, f"Failed to read trajectory CSV: {e}"
    return health_counts, total_rows, None


def _check_manifest_consistency(manifest_path: Path, health_counts: dict[str, int]) -> str | None:
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest_health = manifest.get("health_counts", {})
        for h in ["OK", "DEGRADED", "LOST", "INVALID"]:
            m_count = manifest_health.get(h, 0)
            c_count = health_counts.get(h, 0)
            if m_count != c_count:
                return f"Health count mismatch for '{h}': manifest has {m_count}, CSV has {c_count}"
    except Exception as e:
        return f"Failed to check manifest consistency: {e}"
    return None


def _count_tum_rows(tum_path: Path) -> int:
    tum_row_count = 0
    with open(tum_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tum_row_count += 1
    return tum_row_count


def _check_tum_consistency(tum_path: Path, expected_tum_count: int) -> str | None:
    if not tum_path.exists():
        return None
    try:
        tum_row_count = _count_tum_rows(tum_path)
    except Exception as e:
        return f"Failed to check TUM consistency: {e}"
    if tum_row_count != expected_tum_count:
        return f"TUM row count {tum_row_count} does not match OK+DEGRADED count {expected_tum_count}"
    return None


def _check_metrics_consistency(metrics_path: Path, total_trajectory_rows: int) -> str | None:
    if not metrics_path.exists():
        return None
    try:
        with open(metrics_path, encoding="utf-8") as f:
            metrics_data = json.load(f)

        total_est_poses = _metrics_pose_count(metrics_data)

        if total_est_poses != total_trajectory_rows:
            return (
                f"metrics.json pose count {total_est_poses} does not match trajectory row count {total_trajectory_rows}"
            )
    except Exception as e:
        return f"Failed to check metrics consistency: {e}"
    return None


def _metrics_pose_count(metrics_data: dict[str, Any]) -> int | None:
    coverage_count = metrics_data.get("coverage", {}).get("total_estimate_poses")
    if coverage_count is not None:
        return coverage_count
    failures = metrics_data.get("failures", {})
    if failures:
        return sum(
            failures.get(k, 0)
            for k in ["ok_pose_count", "degraded_pose_count", "lost_pose_count", "invalid_pose_count"]
        )
    return metrics_data.get("runtime", {}).get("update_count")


def _cross_consistency_error(
    manifest_path: Path, trajectory_path: Path, tum_path: Path, metrics_path: Path
) -> str | None:
    health_counts, total_rows, err = _load_trajectory_health(trajectory_path)
    if err:
        return err

    err = _check_manifest_consistency(manifest_path, health_counts)
    if err:
        return err

    expected_tum = health_counts["OK"] + health_counts["DEGRADED"]
    err = _check_tum_consistency(tum_path, expected_tum)
    if err:
        return err

    return _check_metrics_consistency(metrics_path, total_rows)


def check_cross_consistency(run_dir: str | Path) -> ValidationResult:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    trajectory_path = run_dir / "estimated_trajectory.csv"
    tum_path = run_dir / "estimated_trajectory_tum.txt"
    metrics_path = run_dir / "metrics.json"

    if not trajectory_path.exists():
        return ValidationResult(
            "check_cross_consistency", False, "Missing estimated_trajectory.csv for cross-consistency check"
        )

    err = _cross_consistency_error(manifest_path, trajectory_path, tum_path, metrics_path)
    if err:
        return ValidationResult("check_cross_consistency", False, err)

    return ValidationResult("check_cross_consistency", True, "All cross-consistency checks passed")


def _baseline_validation_results(run_dir: Path) -> list[ValidationResult]:
    return [
        check_trajectory_csv(run_dir / "estimated_trajectory.csv"),
        check_tum_file(run_dir / "estimated_trajectory_tum.txt"),
        check_run_manifest(run_dir / "run_manifest.json"),
        check_failure_notes(run_dir / "failure_notes.md"),
        check_run_log(run_dir / "run.log"),
    ]


def _first_existing_plot(run_dir: Path, stem: str) -> Path | None:
    for ext in [".png", ".svg"]:
        path = run_dir / f"{stem}{ext}"
        if path.exists():
            return path
    return None


def _plot_validation_result(run_dir: Path, stem: str, missing_message: str) -> ValidationResult:
    plot_path = _first_existing_plot(run_dir, stem)
    if plot_path is None:
        return ValidationResult("check_plot_file", False, missing_message)
    return check_plot_file(plot_path)


def _evaluation_validation_results(run_dir: Path) -> list[ValidationResult]:
    return [
        check_metrics_json(run_dir / "metrics.json"),
        check_error_vs_time_csv(run_dir / "error_vs_time.csv"),
        check_error_vs_distance_csv(run_dir / "error_vs_distance.csv"),
        _plot_validation_result(run_dir, "trajectory_plot", "Missing trajectory_plot.png or trajectory_plot.svg"),
        _plot_validation_result(run_dir, "drift_plot", "Missing drift_plot.png or drift_plot.svg"),
    ]


def validate_run_directory(run_dir: str | Path, expect_eval: bool = True) -> tuple[list[ValidationResult], bool]:
    run_dir = Path(run_dir)
    results = _baseline_validation_results(run_dir)
    if expect_eval:
        results.extend(_evaluation_validation_results(run_dir))
    results.append(check_cross_consistency(run_dir))

    all_passed = all(r.passed for r in results)
    return results, all_passed
