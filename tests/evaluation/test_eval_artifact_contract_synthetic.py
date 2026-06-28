import csv
import json

import numpy as np

from nav_benchmark.evaluation.metrics import (
    EvalConfig,
    evaluate_trajectory,
    export_error_vs_distance_csv,
    export_error_vs_time_csv,
    export_metrics_json,
)
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


def test_evaluation_artifact_contracts(tmp_path):
    """
    Verifies that the evaluator exports the correct schema and formats
    for metrics.json, error_vs_time.csv, and error_vs_distance.csv.
    """
    # Create synthetic trajectory estimate and ground truth
    timestamps = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    # Estimate has some drift
    est_positions = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.1, 0.0],
            [2.0, 0.8, 0.1],
            [3.0, 0.9, 0.3],
            [4.0, 1.4, 0.6],
            [5.0, 1.5, 1.0],
        ]
    )
    # Ground truth uses a non-collinear 3D path so SE(3) alignment is well-conditioned.
    gt_positions = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.6, 0.0],
            [3.0, 0.6, 0.2],
            [4.0, 1.0, 0.4],
            [5.0, 1.0, 0.8],
        ]
    )
    orientations = np.array([[0.0, 0.0, 0.0, 1.0]] * 6)
    health = np.array(
        [PoseHealth.OK, PoseHealth.OK, PoseHealth.DEGRADED, PoseHealth.DEGRADED, PoseHealth.LOST, PoseHealth.LOST]
    )

    estimate = Trajectory(
        timestamps=timestamps,
        method="imu_only",
        positions=est_positions,
        orientations=orientations,
        health=health,
    )

    reference = Trajectory(
        timestamps=timestamps,
        method="ground_truth",
        positions=gt_positions,
        orientations=orientations,
    )

    config = EvalConfig(alignment_policy="se3", association_tolerance_sec=0.1)
    res = evaluate_trajectory(estimate, reference, config)

    # 1. Test metrics.json contract
    metrics_json_path = tmp_path / "metrics.json"
    export_metrics_json(res, metrics_json_path)
    assert metrics_json_path.exists()

    with open(metrics_json_path) as f:
        metrics_data = json.load(f)

    assert metrics_data["status"] == "OK"
    assert "config" in metrics_data
    assert "metrics" in metrics_data
    assert "alignment" in metrics_data
    assert "diagnostics" in metrics_data
    assert "coverage" in metrics_data
    assert "drift_bins" in metrics_data

    # Verify that nan/inf are replaced with null in json
    # (Checking float serialization robustness)
    def check_no_nan_inf(val):
        if isinstance(val, float):
            assert np.isfinite(val)
        elif isinstance(val, dict):
            for v in val.values():
                check_no_nan_inf(v)
        elif isinstance(val, list):
            for v in val:
                check_no_nan_inf(v)

    check_no_nan_inf(metrics_data)

    # 2. Test error_vs_time.csv contract
    evt_path = tmp_path / "error_vs_time.csv"
    export_error_vs_time_csv(res, evt_path)
    assert evt_path.exists()

    with open(evt_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    expected_evt_header = [
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
    assert header == expected_evt_header
    assert len(rows) == len(timestamps)

    # Verify health states are preserved in output
    health_col_idx = header.index("health")
    row_health_vals = [r[health_col_idx] for r in rows]
    assert row_health_vals == ["OK", "OK", "DEGRADED", "DEGRADED", "LOST", "LOST"]

    # 3. Test error_vs_distance.csv contract
    evd_path = tmp_path / "error_vs_distance.csv"
    export_error_vs_distance_csv(res, evd_path)
    assert evd_path.exists()

    with open(evd_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    expected_evd_header = [
        "cumulative_distance",
        "error_magnitude",
        "health",
        "association_residual",
        "bin_start",
        "bin_end",
    ]
    assert header == expected_evd_header
