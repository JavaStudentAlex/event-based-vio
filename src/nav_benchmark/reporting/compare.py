"""Multi-run method comparison: aggregate evaluated run directories into one report.

Consumes the standard per-run artifacts (``run_manifest.json`` + ``metrics.json``)
and produces ``metrics_comparison.json``, ``comparison_table.csv``, and a
drift-versus-distance comparison plot.
"""

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from nav_benchmark.evaluation.plots import write_method_drift_comparison_plot

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
    "latency_mean_ms",
    "latency_p95_ms",
    "real_time_factor",
)


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


def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


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


def _drift_bins_by_method(summaries: list[RunSummary]) -> dict[str, list[dict[str, Any]]]:
    by_method: dict[str, list[dict[str, Any]]] = {}
    for summary in summaries:
        label = summary.method if summary.method not in by_method else f"{summary.method} ({summary.run_dir})"
        by_method[label] = summary.drift_bins
    return by_method


def write_comparison_artifacts(summaries: list[RunSummary], output_dir: str | Path) -> dict[str, Path]:
    """Write metrics_comparison.json, comparison_table.csv, and the drift comparison plot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "metrics_comparison.json"
    table_path = output_dir / "comparison_table.csv"
    plot_base = output_dir / "backend_comparison_drift"

    _write_comparison_json(summaries, json_path)
    _write_comparison_table(summaries, table_path)
    write_method_drift_comparison_plot(_drift_bins_by_method(summaries), plot_base)

    return {
        "metrics_comparison": json_path,
        "comparison_table": table_path,
        "drift_plot": plot_base.with_suffix(".png"),
    }
