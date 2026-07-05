import csv
import json

import numpy as np
import pytest

from nav_benchmark.evaluation.metrics import (
    EvalConfig,
    EvaluationError,
    evaluate_trajectory,
    export_error_vs_distance_csv,
    export_error_vs_time_csv,
    export_metrics_json,
    make_json_serializable,
    read_project_csv,
)
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


def test_read_project_csv_valid(tmp_path):
    csv_path = tmp_path / "valid_traj.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
        )
        writer.writerow([100.0, "imu_only", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3, 0.9, "OK", 5.0])
        writer.writerow([100.1, "imu_only", 1.1, 2.1, 3.1, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3, 0.8, "DEGRADED", 6.0])

    traj = read_project_csv(csv_path)
    assert traj.method == "imu_only"
    np.testing.assert_allclose(traj.timestamps, [100.0, 100.1])
    np.testing.assert_allclose(traj.positions[0], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(traj.orientations[0], [0.0, 0.0, 0.0, 1.0])
    assert traj.health[0] == "OK"
    assert traj.health[1] == "DEGRADED"
    np.testing.assert_allclose(traj.latency_ms, [5.0, 6.0])


def test_read_project_csv_invalid_header(tmp_path):
    csv_path = tmp_path / "invalid_header.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "method", "x", "y", "z"])  # missing orientations
        writer.writerow([100.0, "imu_only", 1.0, 2.0, 3.0])

    with pytest.raises(EvaluationError, match="Missing required columns"):
        read_project_csv(csv_path)


def test_read_project_csv_non_finite(tmp_path):
    csv_path = tmp_path / "non_finite.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
        )
        writer.writerow([100.0, "imu_only", float("nan"), 2.0, 3.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3, 0.9, "OK", 5.0])

    with pytest.raises(EvaluationError, match="Non-finite value"):
        read_project_csv(csv_path)


def test_read_project_csv_non_monotonic(tmp_path):
    csv_path = tmp_path / "non_monotonic.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
        )
        writer.writerow([100.0, "imu_only", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3, 0.9, "OK", 5.0])
        writer.writerow([99.9, "imu_only", 1.1, 2.1, 3.1, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3, 0.8, "OK", 6.0])

    with pytest.raises(EvaluationError, match="Timestamps are not strictly monotonic"):
        read_project_csv(csv_path)


def test_read_project_csv_invalid_health(tmp_path):
    csv_path = tmp_path / "invalid_health.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
        )
        writer.writerow([100.0, "imu_only", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3, 0.9, "UNKNOWN", 5.0])

    with pytest.raises(EvaluationError, match="Invalid health value"):
        read_project_csv(csv_path)


def test_evaluate_trajectory_perfect_alignment():
    # 4 points forming a non-collinear shape (T-shape/corner) to avoid degenerate covariance
    ref_ts = np.array([10.0, 11.0, 12.0, 13.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)  # xyzw: identity

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    # Shift and rotate estimate: 90 deg around Z, translate by [1, 2, 3]
    # R_z(90): x_new = -y, y_new = x, z_new = z
    # Then translate: x_new + 1, y_new + 2, z_new + 3
    # Pos 0: [0, 0, 0] -> [1, 2, 3]
    # Pos 1: [1, 0, 0] -> [1, 3, 3]
    # Pos 2: [0, 1, 0] -> [0, 2, 3]
    # Pos 3: [0, 0, 1] -> [1, 2, 4]
    est_pos = np.array([[1.0, 2.0, 3.0], [1.0, 3.0, 3.0], [0.0, 2.0, 3.0], [1.0, 2.0, 4.0]])
    # R_z(90) quaternion (xyzw): [0, 0, 0.70710678, 0.70710678]
    est_ori = np.array([[0.0, 0.0, 0.70710678, 0.70710678]] * 4)

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=est_pos,
        orientations=est_ori,
    )

    config = EvalConfig(alignment_policy="se3", association_tolerance_sec=0.1)
    res = evaluate_trajectory(estimate, reference, config)

    assert res.status == "OK"
    assert res.metrics.ate_rmse < 1e-5
    assert res.metrics.ate_mean < 1e-5
    assert res.metrics.final_drift < 1e-5

    # Check R & t
    # T_est_to_ref:
    # R should be R_z(-90) because we transform estimate to reference
    R = np.array(res.alignment.R)
    t = np.array(res.alignment.t)

    # R_z(-90) rotates [1, 0, 0] to [0, -1, 0]
    expected_R = np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    # Translate should be [-2, 1, -3]
    np.testing.assert_allclose(R, expected_R, atol=1e-5)
    np.testing.assert_allclose(t, [-2.0, 1.0, -3.0], atol=1e-5)


def test_evaluate_trajectory_known_drift():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 5)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    # Estimate drifts in x direction by 0.1m per meter
    est_pos = np.array([[0.0, 0.0, 0.0], [1.1, 0.0, 0.0], [2.2, 0.0, 0.0], [3.3, 0.0, 0.0], [4.4, 0.0, 0.0]])
    est_ori = ref_ori.copy()

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=est_pos,
        orientations=est_ori,
    )

    # Use alignment_policy="none" to measure exact drift
    config = EvalConfig(alignment_policy="none", rpe_delta_m=1.0)
    res = evaluate_trajectory(estimate, reference, config)

    assert res.status == "OK"
    np.testing.assert_allclose(res.metrics.ate_rmse, np.sqrt(np.mean([0.0, 0.1**2, 0.2**2, 0.3**2, 0.4**2])))
    assert abs(res.metrics.final_drift - 0.4) < 1e-5
    assert abs(res.metrics.cumulative_distance - 4.4) < 1e-5
    # drift_percent = final_drift / cumulative_distance * 100 = 0.4 / 4.4 * 100
    np.testing.assert_allclose(res.metrics.drift_percent, 0.4 / 4.4 * 100.0, atol=1e-4)
    # Identical identity orientations mean zero heading error.
    assert res.metrics.heading_error_mean_deg == pytest.approx(0.0, abs=1e-9)
    assert res.metrics.heading_error_p95_deg == pytest.approx(0.0, abs=1e-9)


def test_evaluate_trajectory_error_at_distance_markers():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 5)
    reference = Trajectory(timestamps=ref_ts, method="gt", positions=ref_pos, orientations=ref_ori)

    est_pos = np.array([[0.0, 0.0, 0.0], [1.1, 0.0, 0.0], [2.2, 0.0, 0.0], [3.3, 0.0, 0.0], [4.4, 0.0, 0.0]])
    estimate = Trajectory(timestamps=ref_ts, method="imu_only", positions=est_pos, orientations=ref_ori.copy())

    config = EvalConfig(alignment_policy="none", distance_markers_m=(2.0, 4.0, 100.0))
    res = evaluate_trajectory(estimate, reference, config)

    assert res.status == "OK"
    # Cumulative estimate distances are [0, 1.1, 2.2, 3.3, 4.4]; the first pose at >= 2 m
    # is index 2 (error 0.2) and at >= 4 m index 4 (error 0.4). 100 m is never reached.
    assert res.metrics.error_at_distance_m["2"] == pytest.approx(0.2, abs=1e-9)
    assert res.metrics.error_at_distance_m["4"] == pytest.approx(0.4, abs=1e-9)
    assert res.metrics.error_at_distance_m["100"] is None


def test_evaluate_trajectory_known_heading_error():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)
    reference = Trajectory(timestamps=ref_ts, method="gt", positions=ref_pos, orientations=ref_ori)

    # Estimate yawed by a constant +10 degrees around Z.
    yaw_rad = np.deg2rad(10.0)
    q = [0.0, 0.0, np.sin(yaw_rad / 2.0), np.cos(yaw_rad / 2.0)]
    est_ori = np.array([q] * 4)
    estimate = Trajectory(timestamps=ref_ts, method="imu_only", positions=ref_pos.copy(), orientations=est_ori)

    config = EvalConfig(alignment_policy="none")
    res = evaluate_trajectory(estimate, reference, config)

    assert res.status == "OK"
    assert res.metrics.heading_error_mean_deg == pytest.approx(10.0, abs=1e-6)
    assert res.metrics.heading_error_p95_deg == pytest.approx(10.0, abs=1e-6)
    assert res.metrics.drift_percent == pytest.approx(0.0, abs=1e-9)


def test_runtime_metrics_report_real_time_factor():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)
    reference = Trajectory(timestamps=ref_ts, method="gt", positions=ref_pos, orientations=ref_ori)

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=ref_pos.copy(),
        orientations=ref_ori.copy(),
        latency_ms=np.full(4, 250.0),
    )

    res = evaluate_trajectory(estimate, reference, EvalConfig(alignment_policy="none"))

    assert res.runtime.duration_sec == pytest.approx(3.0)
    # 4 samples x 250 ms = 1 s of processing over a 3 s sequence.
    assert res.runtime.total_processing_time_sec == pytest.approx(1.0)
    assert res.runtime.real_time_factor == pytest.approx(3.0)


def test_runtime_metrics_without_latency_have_no_real_time_factor():
    ref_ts = np.array([0.0, 1.0, 2.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 3)
    reference = Trajectory(timestamps=ref_ts, method="gt", positions=ref_pos, orientations=ref_ori)
    estimate = Trajectory(timestamps=ref_ts, method="imu_only", positions=ref_pos.copy(), orientations=ref_ori.copy())

    res = evaluate_trajectory(estimate, reference, EvalConfig(alignment_policy="none"))

    assert res.runtime.total_processing_time_sec is None
    assert res.runtime.real_time_factor is None


def test_evaluate_trajectory_coverage():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 5)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    # Estimate has mixed health
    est_health = np.array(
        [
            PoseHealth.OK,  # duration: 1.0
            PoseHealth.DEGRADED,  # duration: 1.0
            PoseHealth.LOST,  # duration: 1.0
            PoseHealth.INVALID,  # duration: 1.0
            PoseHealth.OK,  # duration: 1.0 (inherits last dt)
        ],
        dtype=object,
    )

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=ref_pos.copy(),
        orientations=ref_ori.copy(),
        health=est_health,
    )

    config = EvalConfig(alignment_policy="none")
    res = evaluate_trajectory(estimate, reference, config)

    assert res.status == "OK"
    cov = res.coverage
    assert cov.total_duration_sec == 4.0
    assert cov.ok_duration_sec == 2.0
    assert cov.degraded_duration_sec == 1.0
    assert cov.lost_duration_sec == 1.0
    assert cov.invalid_duration_sec == 1.0
    assert cov.ok_fraction == 0.5
    assert cov.lost_fraction == 0.25
    assert cov.invalid_fraction == 0.25


def test_evaluate_trajectory_runtime_and_failure_counts():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    ref_pos = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [3.0, 1.0, 0.0],
            [3.0, 1.0, 1.0],
        ]
    )
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 6)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    health = np.array(
        [
            PoseHealth.OK,
            PoseHealth.LOST,
            PoseHealth.INVALID,
            PoseHealth.OK,
            PoseHealth.DEGRADED,
            PoseHealth.LOST,
        ],
        dtype=object,
    )
    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=ref_pos.copy(),
        orientations=ref_ori.copy(),
        health=health,
        latency_ms=np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
    )

    res = evaluate_trajectory(estimate, reference, EvalConfig(alignment_policy="none"))

    assert res.runtime.update_count == 6
    assert res.runtime.duration_sec == 5.0
    assert res.runtime.odometry_frequency_hz == 1.0
    assert res.runtime.latency_mean_ms == 3.5
    assert res.runtime.latency_median_ms == 3.5
    assert res.runtime.latency_max_ms == 6.0

    assert res.failures.lost_pose_count == 2
    assert res.failures.invalid_pose_count == 1
    assert res.failures.failed_frame_count == 3
    assert res.failures.failed_window_count == 2
    assert res.failures.failed_duration_sec == 3.0


def test_evaluate_trajectory_insufficient_pairs():
    ref_ts = np.array([0.0, 1.0, 2.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 3)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    # Estimate has only 2 OK/DEGRADED points
    est_health = np.array([PoseHealth.OK, PoseHealth.LOST, PoseHealth.INVALID], dtype=object)
    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=ref_pos.copy(),
        orientations=ref_ori.copy(),
        health=est_health,
    )

    config = EvalConfig()
    with pytest.raises(EvaluationError, match="Insufficient OK/DEGRADED poses"):
        evaluate_trajectory(estimate, reference, config)


def test_evaluate_trajectory_non_finite():
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    est_pos = ref_pos.copy()
    est_pos[2, 0] = float("nan")

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=est_pos,
        orientations=ref_ori.copy(),
    )

    config = EvalConfig()
    with pytest.raises(EvaluationError, match="contain non-finite values"):
        evaluate_trajectory(estimate, reference, config)


def test_json_serialization(tmp_path):
    ref_ts = np.array([0.0, 1.0, 2.0, 3.0])
    ref_pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    ref_ori = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)

    reference = Trajectory(
        timestamps=ref_ts,
        method="gt",
        positions=ref_pos,
        orientations=ref_ori,
    )

    # Add a nan into velocity to verify serialization cleans it
    est_vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [float("nan"), 0.0, 0.0]])

    estimate = Trajectory(
        timestamps=ref_ts,
        method="imu_only",
        positions=ref_pos.copy(),
        orientations=ref_ori.copy(),
        velocities=est_vel,
    )

    config = EvalConfig(alignment_policy="none")
    res = evaluate_trajectory(estimate, reference, config)

    # Let's verify make_json_serializable converts nan to None
    serializable = make_json_serializable(res)
    json_str = json.dumps(serializable)
    loaded = json.loads(json_str)

    assert loaded["status"] == "OK"
    assert loaded["metrics"]["ate_rmse"] == 0.0

    # Test file exports
    export_metrics_json(res, tmp_path / "metrics.json")
    export_error_vs_time_csv(res, tmp_path / "error_vs_time.csv")
    export_error_vs_distance_csv(res, tmp_path / "error_vs_distance.csv")

    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "error_vs_time.csv").exists()
    assert (tmp_path / "error_vs_distance.csv").exists()
