from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from nav_benchmark.evaluation.metrics import EvaluationResult
from nav_benchmark.trajectory.models import Trajectory


class PlottingError(ValueError):
    """Exception raised when plotting preconditions fail or plot cannot be generated."""

    pass


def _plot_output_paths(output_path: str | Path) -> tuple[Path, Path]:
    path = Path(output_path)
    png_path = path.with_suffix(".png")
    svg_path = path.with_suffix(".svg")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    return png_path, svg_path


def _title_lines(default_title: str, title: str | None, sequence: str | None) -> str:
    title_parts = [title or default_title]
    if sequence:
        title_parts.append(f"Sequence: {sequence}")
    return "\n".join(title_parts)


def _save_png_and_svg(fig, png_path: Path, svg_path: Path, description: str) -> None:
    try:
        fig.savefig(png_path, dpi=300)
        fig.savefig(svg_path)
    except Exception as e:
        raise PlottingError(f"Failed to save {description} plot files: {e}") from e
    finally:
        plt.close(fig)


def _method_name(result: EvaluationResult) -> str:
    if result.aligned_estimate and result.aligned_estimate.method:
        return result.aligned_estimate.method
    return "unknown"


def _plot_start_end_markers(ax, positions: np.ndarray, size: int = 80) -> None:
    if len(positions) == 0:
        return
    ax.scatter(positions[0, 0], positions[0, 1], color="green", marker="o", s=size, label="Start", zorder=5)
    ax.scatter(positions[-1, 0], positions[-1, 1], color="red", marker="x", s=size, label="End", zorder=5)


def _apply_xy_axes(ax) -> None:
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.grid(True, linestyle=":", alpha=0.6)


def _require_trajectory_plot_inputs(result: EvaluationResult) -> None:
    if result is None:
        raise PlottingError("Evaluation result cannot be None")
    if _missing_trajectory(result.aligned_estimate):
        raise PlottingError("Aligned estimate trajectory is missing or empty")
    if _missing_trajectory(result.aligned_ground_truth):
        raise PlottingError("Aligned ground-truth trajectory is missing or empty")


def _missing_trajectory(trajectory: Trajectory | None) -> bool:
    return trajectory is None or len(trajectory.timestamps) == 0


def write_trajectory_plot(
    result: EvaluationResult,
    output_path: str | Path,
    sequence: str | None = None,
    title: str | None = None,
) -> None:
    """
    Plots the estimated trajectory against aligned ground truth and saves as PNG and SVG.

    Uses equal XY aspect ratio, labels axes in meters, and includes method/sequence metadata.
    """
    _require_trajectory_plot_inputs(result)
    png_path, svg_path = _plot_output_paths(output_path)

    fig, ax = plt.subplots(figsize=(8, 6))

    if result.aligned_ground_truth is None or result.aligned_estimate is None:
        raise PlottingError("Missing aligned trajectories")

    gt_pos = result.aligned_ground_truth.positions
    est_pos = result.aligned_estimate.positions

    # Plot ground truth
    ax.plot(
        gt_pos[:, 0],
        gt_pos[:, 1],
        label="Ground Truth",
        color="black",
        linestyle="--",
        linewidth=1.5,
    )

    # Plot estimate
    method_name = result.aligned_estimate.method
    ax.plot(
        est_pos[:, 0],
        est_pos[:, 1],
        label=f"Estimate ({method_name})",
        color="blue",
        linewidth=1.5,
    )

    _plot_start_end_markers(ax, gt_pos)
    _apply_xy_axes(ax)
    ax.set_title(_title_lines(f"Trajectory Alignment ({method_name})", title, sequence))
    ax.legend()

    fig.tight_layout()
    _save_png_and_svg(fig, png_path, svg_path, "trajectory")


def _valid_drift_bins(result: EvaluationResult):
    _require_drift_plot_inputs(result)
    return _drift_bins_with_medians(result)


def _require_drift_plot_inputs(result: EvaluationResult) -> None:
    if result is None:
        raise PlottingError("Evaluation result cannot be None")
    if not result.error_vs_distance:
        raise PlottingError("Error vs distance data is missing or empty")
    if not result.drift_bins:
        raise PlottingError("Drift bin summaries are missing or empty")


def _drift_bins_with_medians(result: EvaluationResult):
    valid_bins = [bin_summary for bin_summary in result.drift_bins if bin_summary.median_error is not None]
    if not valid_bins:
        raise PlottingError("No valid drift bin data to plot")
    return valid_bins


def _plot_drift_raw_errors(ax, result: EvaluationResult) -> None:
    dists = [row.cumulative_distance for row in result.error_vs_distance]
    errors = [row.error_magnitude for row in result.error_vs_distance]
    ax.plot(
        dists,
        errors,
        color="lightblue",
        alpha=0.7,
        linewidth=1.0,
        label="Raw ATE [m]",
    )


def _plot_drift_bin_summaries(ax, drift_bins) -> None:
    median_labeled = False
    iqr_labeled = False
    for bin_sum in drift_bins:
        if bin_sum.median_error is None or bin_sum.iqr_error is None:
            continue
        _plot_drift_bin(ax, bin_sum, median_labeled, iqr_labeled)
        median_labeled = True
        iqr_labeled = True


def _plot_drift_bin(ax, bin_sum, median_labeled: bool, iqr_labeled: bool) -> None:
    xs = [bin_sum.bin_start, bin_sum.bin_end]
    y_low = max(0.0, bin_sum.median_error - bin_sum.iqr_error / 2.0)
    y_high = bin_sum.median_error + bin_sum.iqr_error / 2.0

    ax.plot(
        xs,
        [bin_sum.median_error, bin_sum.median_error],
        color="red",
        linewidth=2.5,
        zorder=4,
        label="20m Bin Median" if not median_labeled else None,
    )
    ax.fill_between(
        xs,
        [y_low, y_low],
        [y_high, y_high],
        color="red",
        alpha=0.2,
        zorder=3,
        label="20m Bin IQR Band" if not iqr_labeled else None,
    )


def write_drift_over_distance_plot(
    result: EvaluationResult,
    output_path: str | Path,
    sequence: str | None = None,
    title: str | None = None,
) -> None:
    """
    Plots position error over cumulative distance and overlays drift-bin summaries.

    Saves the plots in both PNG and SVG formats.
    """
    valid_bins = _valid_drift_bins(result)
    png_path, svg_path = _plot_output_paths(output_path)

    fig, ax = plt.subplots(figsize=(8, 6))

    _plot_drift_raw_errors(ax, result)
    _plot_drift_bin_summaries(ax, valid_bins)
    ax.set_xlabel("Cumulative Distance [m]")
    ax.set_ylabel("Position Error (ATE) [m]")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.set_title(_title_lines(f"Drift over Distance ({_method_name(result)})", title, sequence))
    ax.legend()

    fig.tight_layout()
    _save_png_and_svg(fig, png_path, svg_path, "drift")


def _plot_trajectory_comparison_lines(ax, trajectories: dict[str, Trajectory]) -> None:
    for method, trajectory in trajectories.items():
        if len(trajectory.timestamps) == 0:
            continue
        pos = trajectory.positions
        ax.plot(pos[:, 0], pos[:, 1], label=method, linewidth=1.3)


def write_trajectory_comparison_plot(
    trajectories: dict[str, Trajectory],
    ground_truth: Trajectory,
    output_path: str | Path,
    sequence: str | None = None,
    title: str | None = None,
) -> None:
    """Write a multi-method XY trajectory comparison plot."""
    if not trajectories:
        raise PlottingError("At least one trajectory is required for comparison plotting")
    if len(ground_truth.timestamps) == 0:
        raise PlottingError("Ground-truth trajectory is empty")

    png_path, svg_path = _plot_output_paths(output_path)

    fig, ax = plt.subplots(figsize=(9, 7))
    gt_pos = ground_truth.positions
    ax.plot(gt_pos[:, 0], gt_pos[:, 1], label="Ground Truth", color="black", linestyle="--", linewidth=1.8)

    _plot_trajectory_comparison_lines(ax, trajectories)
    _plot_start_end_markers(ax, gt_pos, size=70)
    _apply_xy_axes(ax)
    ax.set_title(_title_lines("Trajectory Comparison", title, sequence))
    ax.legend()
    fig.tight_layout()
    _save_png_and_svg(fig, png_path, svg_path, "trajectory comparison")


def write_ensemble_weight_plot(
    ensemble: Trajectory,
    output_path: str | Path,
    sequence: str | None = None,
    title: str | None = None,
) -> None:
    """Plot logged confidence-fusion weights from an ensemble trajectory."""
    weight_columns = [name for name in ("w_imu", "w_rgb", "w_event", "w_event_imu") if name in ensemble.extra_columns]
    if not weight_columns:
        raise PlottingError("Ensemble trajectory has no weight columns to plot")

    png_path, svg_path = _plot_output_paths(output_path)

    fig, ax = plt.subplots(figsize=(9, 5))
    t = np.asarray(ensemble.timestamps, dtype=np.float64)
    for column in weight_columns:
        ax.plot(t, ensemble.extra_columns[column], label=column, linewidth=1.5)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Normalized Fusion Weight")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.set_title(_title_lines("Ensemble Weights", title, sequence))
    ax.legend()
    fig.tight_layout()
    _save_png_and_svg(fig, png_path, svg_path, "ensemble weight")
