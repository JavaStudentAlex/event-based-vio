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
    if result is None:
        raise PlottingError("Evaluation result cannot be None")
    if result.aligned_estimate is None or len(result.aligned_estimate.timestamps) == 0:
        raise PlottingError("Aligned estimate trajectory is missing or empty")
    if result.aligned_ground_truth is None or len(result.aligned_ground_truth.timestamps) == 0:
        raise PlottingError("Aligned ground-truth trajectory is missing or empty")

    path = Path(output_path)
    png_path = path.with_suffix(".png")
    svg_path = path.with_suffix(".svg")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))

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

    # Plot start and end markers
    if len(gt_pos) > 0:
        ax.scatter(gt_pos[0, 0], gt_pos[0, 1], color="green", marker="o", s=80, label="Start", zorder=5)
        ax.scatter(gt_pos[-1, 0], gt_pos[-1, 1], color="red", marker="x", s=80, label="End", zorder=5)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.grid(True, linestyle=":", alpha=0.6)

    # Build title with metadata
    title_parts = []
    if title:
        title_parts.append(title)
    else:
        title_parts.append(f"Trajectory Alignment ({method_name})")

    if sequence:
        title_parts.append(f"Sequence: {sequence}")

    ax.set_title("\n".join(title_parts))
    ax.legend()

    fig.tight_layout()

    try:
        fig.savefig(png_path, dpi=300)
        fig.savefig(svg_path)
    except Exception as e:
        raise PlottingError(f"Failed to save trajectory plot files: {e}") from e
    finally:
        plt.close(fig)


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
    if result is None:
        raise PlottingError("Evaluation result cannot be None")
    if not result.error_vs_distance:
        raise PlottingError("Error vs distance data is missing or empty")
    if not result.drift_bins:
        raise PlottingError("Drift bin summaries are missing or empty")

    valid_bins = [b for b in result.drift_bins if b.median_error is not None]
    if not valid_bins:
        raise PlottingError("No valid drift bin data to plot")

    path = Path(output_path)
    png_path = path.with_suffix(".png")
    svg_path = path.with_suffix(".svg")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))

    # Extract raw data points
    dists = [row.cumulative_distance for row in result.error_vs_distance]
    errors = [row.error_magnitude for row in result.error_vs_distance]

    # Plot raw error points
    ax.plot(
        dists,
        errors,
        color="lightblue",
        alpha=0.7,
        linewidth=1.0,
        label="Raw ATE [m]",
    )

    # Plot bin summaries
    median_labeled = False
    iqr_labeled = False
    for bin_sum in result.drift_bins:
        if bin_sum.median_error is None or bin_sum.iqr_error is None:
            continue
        xs = [bin_sum.bin_start, bin_sum.bin_end]
        ys_median = [bin_sum.median_error, bin_sum.median_error]
        y_low = bin_sum.median_error - bin_sum.iqr_error / 2.0
        y_high = bin_sum.median_error + bin_sum.iqr_error / 2.0

        # Clip lower boundary to 0 as error magnitude is non-negative
        y_low = max(0.0, y_low)

        med_label = "20m Bin Median" if not median_labeled else None
        iqr_label = "20m Bin IQR Band" if not iqr_labeled else None

        ax.plot(
            xs,
            ys_median,
            color="red",
            linewidth=2.5,
            zorder=4,
            label=med_label,
        )
        ax.fill_between(
            xs,
            [y_low, y_low],
            [y_high, y_high],
            color="red",
            alpha=0.2,
            zorder=3,
            label=iqr_label,
        )

        median_labeled = True
        iqr_labeled = True

    ax.set_xlabel("Cumulative Distance [m]")
    ax.set_ylabel("Position Error (ATE) [m]")
    ax.grid(True, linestyle=":", alpha=0.6)

    # Build title with metadata
    method_name = (
        result.aligned_estimate.method if (result.aligned_estimate and result.aligned_estimate.method) else "unknown"
    )
    title_parts = []
    if title:
        title_parts.append(title)
    else:
        title_parts.append(f"Drift over Distance ({method_name})")

    if sequence:
        title_parts.append(f"Sequence: {sequence}")

    ax.set_title("\n".join(title_parts))
    ax.legend()

    fig.tight_layout()

    try:
        fig.savefig(png_path, dpi=300)
        fig.savefig(svg_path)
    except Exception as e:
        raise PlottingError(f"Failed to save drift plot files: {e}") from e
    finally:
        plt.close(fig)


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

    path = Path(output_path)
    png_path = path.with_suffix(".png")
    svg_path = path.with_suffix(".svg")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 7))
    gt_pos = ground_truth.positions
    ax.plot(gt_pos[:, 0], gt_pos[:, 1], label="Ground Truth", color="black", linestyle="--", linewidth=1.8)

    for method, trajectory in trajectories.items():
        if len(trajectory.timestamps) == 0:
            continue
        pos = trajectory.positions
        ax.plot(pos[:, 0], pos[:, 1], label=method, linewidth=1.3)

    ax.scatter(gt_pos[0, 0], gt_pos[0, 1], color="green", marker="o", s=70, label="Start", zorder=5)
    ax.scatter(gt_pos[-1, 0], gt_pos[-1, 1], color="red", marker="x", s=70, label="End", zorder=5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.grid(True, linestyle=":", alpha=0.6)

    title_parts = [title or "Trajectory Comparison"]
    if sequence:
        title_parts.append(f"Sequence: {sequence}")
    ax.set_title("\n".join(title_parts))
    ax.legend()
    fig.tight_layout()

    try:
        fig.savefig(png_path, dpi=300)
        fig.savefig(svg_path)
    except Exception as e:
        raise PlottingError(f"Failed to save trajectory comparison plot files: {e}") from e
    finally:
        plt.close(fig)


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

    path = Path(output_path)
    png_path = path.with_suffix(".png")
    svg_path = path.with_suffix(".svg")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    t = np.asarray(ensemble.timestamps, dtype=np.float64)
    for column in weight_columns:
        ax.plot(t, ensemble.extra_columns[column], label=column, linewidth=1.5)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Normalized Fusion Weight")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, linestyle=":", alpha=0.6)
    title_parts = [title or "Ensemble Weights"]
    if sequence:
        title_parts.append(f"Sequence: {sequence}")
    ax.set_title("\n".join(title_parts))
    ax.legend()
    fig.tight_layout()

    try:
        fig.savefig(png_path, dpi=300)
        fig.savefig(svg_path)
    except Exception as e:
        raise PlottingError(f"Failed to save ensemble weight plot files: {e}") from e
    finally:
        plt.close(fig)
