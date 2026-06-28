"""Reusable evaluation harness for estimator run directories."""

import csv
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nav_benchmark.datasets.mvsec import load_mvsec_sequence
from nav_benchmark.datasets.synthetic import read_synthetic_ground_truth_csv
from nav_benchmark.evaluation.metrics import (
    EvalConfig,
    EvaluationResult,
    evaluate_trajectory,
    export_error_vs_distance_csv,
    export_error_vs_time_csv,
    export_metrics_json,
    read_project_csv,
)
from nav_benchmark.evaluation.plots import write_drift_over_distance_plot, write_trajectory_plot
from nav_benchmark.trajectory.export import PROJECT_TRAJECTORY_COLUMNS, export_project_csv
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass(frozen=True)
class EvaluationHarnessConfig:
    estimated_filename: str = "estimated_trajectory.csv"
    ground_truth_relative_path: Path = Path("ground_truth") / "trajectory.csv"
    metrics_filename: str = "metrics.json"
    error_vs_time_filename: str = "error_vs_time.csv"
    error_vs_distance_filename: str = "error_vs_distance.csv"
    aligned_ground_truth_filename: str = "ground_truth_aligned.csv"
    trajectory_plot_base: str = "trajectory_plot"
    drift_plot_base: str = "drift_plot"


@dataclass(frozen=True)
class EvaluationArtifactPaths:
    metrics_json: Path
    error_vs_time_csv: Path
    error_vs_distance_csv: Path
    ground_truth_aligned_csv: Path
    trajectory_plot_base: Path
    drift_plot_base: Path


@dataclass
class EvaluationHarnessResult:
    result: EvaluationResult
    estimate_path: Path
    ground_truth_path: Path
    artifacts: EvaluationArtifactPaths


def _manifest_input_path(run_dir: Path) -> Path | None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    input_path = manifest.get("input")
    return Path(input_path) if input_path else None


def resolve_ground_truth_path(
    run_dir: str | Path,
    explicit_path: str | Path | None = None,
    *,
    config: EvaluationHarnessConfig | None = None,
) -> Path:
    """Resolve a ground-truth file from an explicit path, sequence dir, or run manifest."""
    cfg = config or EvaluationHarnessConfig()
    run_dir = Path(run_dir)
    candidate = Path(explicit_path) if explicit_path is not None else _manifest_input_path(run_dir)

    if candidate is None:
        raise FileNotFoundError("Ground truth path not specified and could not be resolved from run_manifest.json")

    if candidate.is_dir():
        gt_path = candidate / cfg.ground_truth_relative_path
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth file not found in sequence directory: {gt_path}")
        return gt_path

    if not candidate.exists():
        raise FileNotFoundError(f"Ground truth file not found: {candidate}")
    return candidate


def load_ground_truth_trajectory(path: str | Path) -> Trajectory:
    """Load ground truth from project CSV, generated synthetic CSV, MVSEC HDF5, or a sequence dir."""
    path = Path(path)
    if path.is_dir():
        path = resolve_ground_truth_path(path, path)

    if path.suffix.lower() in {".h5", ".hdf5"}:
        sequence = load_mvsec_sequence(path)
        if sequence.gt_poses is None or len(sequence.gt_poses) == 0:
            raise ValueError(f"No ground-truth poses found in MVSEC file: {path}")

        gt_poses = sequence.gt_poses
        count = len(gt_poses)
        return Trajectory(
            timestamps=gt_poses["t"],
            method="ground_truth",
            positions=np.stack([gt_poses["x"], gt_poses["y"], gt_poses["z"]], axis=1),
            orientations=np.stack([gt_poses["qx"], gt_poses["qy"], gt_poses["qz"], gt_poses["qw"]], axis=1),
            velocities=np.zeros((count, 3), dtype=np.float64),
            confidence=np.ones(count, dtype=np.float64),
            health=np.array([PoseHealth.OK.value] * count, dtype=object),
            latency_ms=np.zeros(count, dtype=np.float64),
        )

    project_error: Exception | None = None
    try:
        return read_project_csv(path)
    except Exception as err:
        project_error = err

    try:
        return read_synthetic_ground_truth_csv(path)
    except Exception as synthetic_error:
        raise ValueError(
            f"Failed to read ground truth from {path}. "
            f"Project CSV error: {project_error}. Synthetic CSV error: {synthetic_error}"
        ) from synthetic_error


def _write_empty_aligned_ground_truth(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(PROJECT_TRAJECTORY_COLUMNS)


def _artifact_paths(run_dir: Path, config: EvaluationHarnessConfig) -> EvaluationArtifactPaths:
    return EvaluationArtifactPaths(
        metrics_json=run_dir / config.metrics_filename,
        error_vs_time_csv=run_dir / config.error_vs_time_filename,
        error_vs_distance_csv=run_dir / config.error_vs_distance_filename,
        ground_truth_aligned_csv=run_dir / config.aligned_ground_truth_filename,
        trajectory_plot_base=run_dir / config.trajectory_plot_base,
        drift_plot_base=run_dir / config.drift_plot_base,
    )


def write_evaluation_artifacts(
    result: EvaluationResult,
    run_dir: str | Path,
    *,
    sequence: str,
    config: EvaluationHarnessConfig | None = None,
    write_plots: bool = True,
    warn: Callable[[str], None] | None = None,
) -> EvaluationArtifactPaths:
    """Write metrics, error CSVs, aligned ground truth, and plots for an evaluation result."""
    cfg = config or EvaluationHarnessConfig()
    run_dir = Path(run_dir)
    paths = _artifact_paths(run_dir, cfg)

    export_metrics_json(result, paths.metrics_json)
    export_error_vs_time_csv(result, paths.error_vs_time_csv)
    export_error_vs_distance_csv(result, paths.error_vs_distance_csv)

    if result.aligned_ground_truth is not None:
        export_project_csv(result.aligned_ground_truth, paths.ground_truth_aligned_csv)
    else:
        _write_empty_aligned_ground_truth(paths.ground_truth_aligned_csv)

    if write_plots:
        method = result.aligned_estimate.method if result.aligned_estimate is not None else "estimate"
        write_trajectory_plot(
            result,
            paths.trajectory_plot_base,
            sequence=sequence,
            title=f"Trajectory: {method} vs Ground Truth",
        )
        try:
            write_drift_over_distance_plot(
                result,
                paths.drift_plot_base,
                sequence=sequence,
                title=f"Drift over Distance: {method}",
            )
        except Exception as plot_err:
            if warn is not None:
                warn(f"Drift plotting skipped or failed: {plot_err}")

    return paths


def evaluate_run_directory(
    run_dir: str | Path,
    *,
    ground_truth_path: str | Path | None = None,
    eval_config: EvalConfig | None = None,
    harness_config: EvaluationHarnessConfig | None = None,
    sequence: str | None = None,
    write_artifacts: bool = True,
    write_plots: bool = True,
    warn: Callable[[str], None] | None = None,
) -> EvaluationHarnessResult:
    """Evaluate a run directory containing a canonical ``estimated_trajectory.csv``."""
    cfg = harness_config or EvaluationHarnessConfig()
    run_dir = Path(run_dir)
    estimate_path = run_dir / cfg.estimated_filename
    if not estimate_path.exists():
        raise FileNotFoundError(f"Estimated trajectory not found: {estimate_path}")

    resolved_gt_path = resolve_ground_truth_path(run_dir, ground_truth_path, config=cfg)
    estimate = read_project_csv(estimate_path)
    ground_truth = load_ground_truth_trajectory(resolved_gt_path)
    result = evaluate_trajectory(estimate, ground_truth, eval_config or EvalConfig())

    artifacts = _artifact_paths(run_dir, cfg)
    if write_artifacts:
        artifacts = write_evaluation_artifacts(
            result,
            run_dir,
            sequence=sequence or ground_truth.method,
            config=cfg,
            write_plots=write_plots,
            warn=warn,
        )

    return EvaluationHarnessResult(
        result=result,
        estimate_path=estimate_path,
        ground_truth_path=resolved_gt_path,
        artifacts=artifacts,
    )
