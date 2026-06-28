import numpy as np
import pytest

from nav_benchmark.evaluation.metrics import (
    DriftBinSummary,
    ErrorVsDistanceRow,
    EvaluationResult,
)
from nav_benchmark.evaluation.plots import (
    PlottingError,
    write_drift_over_distance_plot,
    write_trajectory_plot,
)
from nav_benchmark.trajectory.models import Trajectory


def test_write_trajectory_plot_success(tmp_path):
    # Setup dummy data for a valid trajectory
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    est_pos = ref_pos + 0.05
    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=est_pos,
        orientations=ref_ori,
    )

    from nav_benchmark.evaluation.metrics import EvalConfig

    result = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        aligned_estimate=estimate,
        aligned_ground_truth=reference,
    )

    output_base = tmp_path / "trajectory_plot"
    write_trajectory_plot(result, output_base, sequence="test_seq", title="Test Title")

    png_path = tmp_path / "trajectory_plot.png"
    svg_path = tmp_path / "trajectory_plot.svg"

    assert png_path.exists()
    assert svg_path.exists()
    assert png_path.stat().st_size > 0
    assert svg_path.stat().st_size > 0

    # Parse SVG and check for expected labels/strings
    svg_content = svg_path.read_text(encoding="utf-8")
    assert "Ground Truth" in svg_content
    assert "Estimate (imu_only)" in svg_content
    assert "Test Title" in svg_content
    assert "Sequence: test_seq" in svg_content
    assert "X [m]" in svg_content
    assert "Y [m]" in svg_content


def test_write_drift_over_distance_plot_success(tmp_path):
    # Setup dummy data for drift evaluation result
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=ref_pos,
        orientations=ref_ori,
    )

    error_vs_distance = [
        ErrorVsDistanceRow(
            cumulative_distance=0.0,
            error_magnitude=0.0,
            health="OK",
            association_residual=0.0,
            bin_start=0.0,
            bin_end=20.0,
        ),
        ErrorVsDistanceRow(
            cumulative_distance=10.0,
            error_magnitude=0.1,
            health="OK",
            association_residual=0.05,
            bin_start=0.0,
            bin_end=20.0,
        ),
        ErrorVsDistanceRow(
            cumulative_distance=20.0,
            error_magnitude=0.2,
            health="OK",
            association_residual=0.02,
            bin_start=20.0,
            bin_end=40.0,
        ),
    ]

    drift_bins = [
        DriftBinSummary(bin_start=0.0, bin_end=20.0, median_error=0.05, iqr_error=0.1, pose_count=2),
        DriftBinSummary(bin_start=20.0, bin_end=40.0, median_error=0.2, iqr_error=0.05, pose_count=1),
    ]

    from nav_benchmark.evaluation.metrics import EvalConfig

    result = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        error_vs_distance=error_vs_distance,
        drift_bins=drift_bins,
        aligned_estimate=estimate,
    )

    output_base = tmp_path / "drift_plot"
    write_drift_over_distance_plot(result, output_base, sequence="test_seq", title="Drift Plot Title")

    png_path = tmp_path / "drift_plot.png"
    svg_path = tmp_path / "drift_plot.svg"

    assert png_path.exists()
    assert svg_path.exists()
    assert png_path.stat().st_size > 0
    assert svg_path.stat().st_size > 0

    svg_content = svg_path.read_text(encoding="utf-8")
    assert "Raw ATE [m]" in svg_content
    assert "20m Bin Median" in svg_content
    assert "20m Bin IQR Band" in svg_content
    assert "Drift Plot Title" in svg_content
    assert "Sequence: test_seq" in svg_content
    assert "Cumulative Distance [m]" in svg_content
    assert "Position Error (ATE) [m]" in svg_content


def test_plotting_negative_cases():
    from nav_benchmark.evaluation.metrics import EvalConfig

    # 1. Result is None
    with pytest.raises(PlottingError, match="result cannot be None"):
        write_trajectory_plot(None, "dummy_path")

    with pytest.raises(PlottingError, match="result cannot be None"):
        write_drift_over_distance_plot(None, "dummy_path")

    # 2. Trajectory plot with missing/empty trajectories
    result_empty_traj = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        aligned_estimate=None,
        aligned_ground_truth=None,
    )
    with pytest.raises(PlottingError, match="Aligned estimate trajectory is missing or empty"):
        write_trajectory_plot(result_empty_traj, "dummy_path")

    empty_t = Trajectory(
        timestamps=np.array([]), method="imu_only", positions=np.empty((0, 3)), orientations=np.empty((0, 4))
    )
    result_empty_traj_2 = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        aligned_estimate=empty_t,
        aligned_ground_truth=empty_t,
    )
    with pytest.raises(PlottingError, match="Aligned estimate trajectory is missing or empty"):
        write_trajectory_plot(result_empty_traj_2, "dummy_path")

    # 3. Drift plot with empty lists or missing bins
    result_no_dist = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        error_vs_distance=[],
        drift_bins=[DriftBinSummary(0.0, 20.0, 0.1, 0.05, 1)],
    )
    with pytest.raises(PlottingError, match="Error vs distance data is missing or empty"):
        write_drift_over_distance_plot(result_no_dist, "dummy_path")

    result_no_bins = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        error_vs_distance=[ErrorVsDistanceRow(0.0, 0.0, "OK", 0.0, 0.0, 20.0)],
        drift_bins=[],
    )
    with pytest.raises(PlottingError, match="Drift bin summaries are missing or empty"):
        write_drift_over_distance_plot(result_no_bins, "dummy_path")

    result_no_valid_bins = EvaluationResult(
        status="OK",
        error_message=None,
        config=EvalConfig(),
        error_vs_distance=[ErrorVsDistanceRow(0.0, 0.0, "OK", 0.0, 0.0, 20.0)],
        drift_bins=[DriftBinSummary(0.0, 20.0, None, None, 0)],
    )
    with pytest.raises(PlottingError, match="No valid drift bin data to plot"):
        write_drift_over_distance_plot(result_no_valid_bins, "dummy_path")
