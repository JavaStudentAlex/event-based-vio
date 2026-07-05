"""Multi-run method comparison: aggregate evaluated run directories into one report.

Consumes the standard per-run artifacts (``run_manifest.json`` + ``metrics.json``,
plus ``estimated_trajectory.csv`` / ``error_vs_time.csv`` when present) and
produces ``metrics_comparison.json``, ``comparison_table.csv``,
``failure_intervals.json``, a drift-versus-distance comparison plot, and a
multi-method trajectory overlay plot.
"""

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from nav_benchmark.evaluation.plots import write_method_drift_comparison_plot, write_trajectory_comparison_plot
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

COMPARISON_TABLE_COLUMNS = (
    "method",
    "sequence",
    "run_dir",
    "status",
    "ate_rmse",
    "rpe_rmse",
    "final_drift",
    "cumulative_distance",
    "drift_percent",
    "ok_fraction",
    "lost_fraction",
    "failed_window_count",
    "failure_interval_count",
    "failure_total_duration_sec",
    "latency_mean_ms",
    "latency_p95_ms",
    "real_time_factor",
)

_FAILURE_STATES = (PoseHealth.DEGRADED.value, PoseHealth.LOST.value, PoseHealth.INVALID.value)


@dataclass(frozen=True)
class RunSummary:
    """Comparable metric snapshot of one evaluated run directory."""

    run_dir: str
    method: str
    sequence: str | None
    status: str
    ate_rmse: float | None
    rpe_rmse: float | None
    final_drift: float | None
    cumulative_distance: float | None
    drift_percent: float | None
    ok_fraction: float | None
    lost_fraction: float | None
    failed_window_count: int | None
    latency_mean_ms: float | None
    latency_p95_ms: float | None
    real_time_factor: float | None
    drift_bins: list[dict[str, Any]]
    failure_interval_count: int | None = None
    failure_total_duration_sec: float | None = None
    failure_intervals: list[dict[str, Any]] = field(default_factory=list)


def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _failure_key(state: str) -> str | None:
    return state if state in _FAILURE_STATES else None


def _intervals_from_labels(timestamps: np.ndarray, labels: list[str]) -> list[dict[str, Any]]:
    """Contiguous runs of failure states; a trailing sentinel closes the last run."""
    intervals: list[dict[str, Any]] = []
    current: str | None = None
    start_time = 0.0
    last_index = len(labels) - 1
    for i, state in enumerate([*labels, ""]):
        key = _failure_key(state)
        if key == current:
            continue
        if current is not None:
            intervals.append(_interval(current, start_time, float(timestamps[i - 1])))
        current = key
        start_time = float(timestamps[min(i, last_index)])
    return intervals


def _failure_intervals_from_run(run_dir: Path) -> list[dict[str, Any]]:
    """Contiguous DEGRADED/LOST/INVALID intervals from the run's estimated trajectory."""
    trajectory_path = run_dir / "estimated_trajectory.csv"
    if not trajectory_path.exists():
        return []
    from nav_benchmark.evaluation.metrics import read_project_csv

    trajectory = read_project_csv(trajectory_path)
    if trajectory.health is None or len(trajectory.timestamps) == 0:
        return []

    timestamps = np.asarray(trajectory.timestamps, dtype=np.float64)
    labels = [str(value) for value in trajectory.health]
    return _intervals_from_labels(timestamps, labels)


def _interval(state: str, t_start: float, t_end: float) -> dict[str, Any]:
    return {
        "state": state,
        "t_start": t_start,
        "t_end": t_end,
        "duration_sec": t_end - t_start,
    }


def load_run_summary(run_dir: str | Path) -> RunSummary:
    """Read one evaluated run directory into a comparable summary."""
    run_dir = Path(run_dir)
    manifest = _load_json(run_dir / "run_manifest.json", "Run manifest")
    metrics_data = _load_json(run_dir / "metrics.json", "Evaluation metrics (run `eval` first)")

    metric_summary = _section(metrics_data, "metrics")
    coverage = _section(metrics_data, "coverage")
    failures = _section(metrics_data, "failures")
    runtime = _section(metrics_data, "runtime")
    drift_bins = metrics_data.get("drift_bins") or []
    failure_intervals = _failure_intervals_from_run(run_dir)

    return RunSummary(
        run_dir=str(run_dir),
        method=str(manifest.get("method", "unknown")),
        sequence=manifest.get("sequence"),
        status=str(metrics_data.get("status", "unknown")),
        ate_rmse=metric_summary.get("ate_rmse"),
        rpe_rmse=metric_summary.get("rpe_rmse"),
        final_drift=metric_summary.get("final_drift"),
        cumulative_distance=metric_summary.get("cumulative_distance"),
        drift_percent=metric_summary.get("drift_percent"),
        ok_fraction=coverage.get("ok_fraction"),
        lost_fraction=coverage.get("lost_fraction"),
        failed_window_count=failures.get("failed_window_count"),
        latency_mean_ms=runtime.get("latency_mean_ms"),
        latency_p95_ms=runtime.get("latency_p95_ms"),
        real_time_factor=runtime.get("real_time_factor"),
        drift_bins=[bin_data for bin_data in drift_bins if isinstance(bin_data, dict)],
        failure_interval_count=len(failure_intervals),
        failure_total_duration_sec=sum(item["duration_sec"] for item in failure_intervals),
        failure_intervals=failure_intervals,
    )


def compare_runs(run_dirs: list[str | Path]) -> list[RunSummary]:
    """Load and order run summaries by drift percentage (best first, unknown last)."""
    if len(run_dirs) < 2:
        raise ValueError("Comparison requires at least two run directories")
    summaries = [load_run_summary(run_dir) for run_dir in run_dirs]
    summaries.sort(key=_ranking_key)
    return summaries


def _ranking_key(summary: RunSummary) -> float:
    if summary.drift_percent is None or not math.isfinite(summary.drift_percent):
        return math.inf
    return float(summary.drift_percent)


def _table_row(summary: RunSummary) -> list[str]:
    values = asdict(summary)
    row = []
    for column in COMPARISON_TABLE_COLUMNS:
        value = values[column]
        row.append("" if value is None else str(value))
    return row


def _write_comparison_table(summaries: list[RunSummary], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COMPARISON_TABLE_COLUMNS)
        writer.writerows(_table_row(summary) for summary in summaries)


def _write_comparison_json(summaries: list[RunSummary], path: Path) -> None:
    payload = {
        "run_count": len(summaries),
        "ranking_by_drift_percent": [summary.method for summary in summaries],
        "runs": [asdict(summary) for summary in summaries],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _summary_labels(summaries: list[RunSummary]) -> list[str]:
    labels: list[str] = []
    for summary in summaries:
        label = summary.method if summary.method not in labels else f"{summary.method} ({summary.run_dir})"
        labels.append(label)
    return labels


def _drift_bins_by_method(summaries: list[RunSummary]) -> dict[str, list[dict[str, Any]]]:
    labels = _summary_labels(summaries)
    return {label: summary.drift_bins for label, summary in zip(labels, summaries, strict=True)}


def _write_failure_intervals_json(summaries: list[RunSummary], path: Path) -> None:
    payload = {
        label: {
            "run_dir": summary.run_dir,
            "interval_count": summary.failure_interval_count,
            "total_duration_sec": summary.failure_total_duration_sec,
            "intervals": summary.failure_intervals,
        }
        for label, summary in zip(_summary_labels(summaries), summaries, strict=True)
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _series_trajectory(timestamps: list[float], xyz: list[list[float]], method: str) -> Trajectory:
    positions = np.asarray(xyz, dtype=np.float64)
    orientations = np.zeros((len(timestamps), 4), dtype=np.float64)
    orientations[:, 3] = 1.0
    return Trajectory(
        timestamps=np.asarray(timestamps, dtype=np.float64),
        method=method,
        positions=positions,
        orientations=orientations,
    )


def _load_error_vs_time_series(run_dir: Path, method: str) -> tuple[Trajectory | None, Trajectory | None]:
    """Aligned estimate and ground-truth series from a run's error_vs_time.csv."""
    path = run_dir / "error_vs_time.csv"
    if not path.exists():
        return None, None
    timestamps: list[float] = []
    est_xyz: list[list[float]] = []
    gt_xyz: list[list[float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Rows without a ground-truth association have empty gt columns; skip them.
            try:
                timestamp = float(row["timestamp"])
                est = [float(row["est_x"]), float(row["est_y"]), float(row["est_z"])]
                gt = [float(row["gt_aligned_x"]), float(row["gt_aligned_y"]), float(row["gt_aligned_z"])]
            except (KeyError, TypeError, ValueError):
                continue
            timestamps.append(timestamp)
            est_xyz.append(est)
            gt_xyz.append(gt)
    if not timestamps:
        return None, None
    return _series_trajectory(timestamps, est_xyz, method), _series_trajectory(timestamps, gt_xyz, "ground_truth")


def _write_trajectory_overlay(summaries: list[RunSummary], plot_base: Path) -> Path | None:
    estimates: dict[str, Trajectory] = {}
    ground_truth: Trajectory | None = None
    for label, summary in zip(_summary_labels(summaries), summaries, strict=True):
        estimate, gt_series = _load_error_vs_time_series(Path(summary.run_dir), label)
        if estimate is None:
            continue
        estimates[label] = estimate
        if ground_truth is None:
            ground_truth = gt_series
    if not estimates or ground_truth is None:
        return None
    write_trajectory_comparison_plot(estimates, ground_truth, plot_base, title="Estimated vs Ground Truth")
    return plot_base.with_suffix(".png")


def write_comparison_artifacts(summaries: list[RunSummary], output_dir: str | Path) -> dict[str, Path]:
    """Write comparison JSON/table, failure intervals, and the comparison plots."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "metrics_comparison.json"
    table_path = output_dir / "comparison_table.csv"
    failure_path = output_dir / "failure_intervals.json"
    plot_base = output_dir / "backend_comparison_drift"

    _write_comparison_json(summaries, json_path)
    _write_comparison_table(summaries, table_path)
    _write_failure_intervals_json(summaries, failure_path)
    write_method_drift_comparison_plot(_drift_bins_by_method(summaries), plot_base)

    artifacts = {
        "metrics_comparison": json_path,
        "comparison_table": table_path,
        "failure_intervals": failure_path,
        "drift_plot": plot_base.with_suffix(".png"),
    }
    overlay_path = _write_trajectory_overlay(summaries, output_dir / "comparison_trajectories")
    if overlay_path is not None:
        artifacts["trajectory_overlay"] = overlay_path
    return artifacts
