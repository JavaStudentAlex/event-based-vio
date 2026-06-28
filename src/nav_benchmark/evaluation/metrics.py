import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from evo.core import metrics as evo_metrics
from evo.core.trajectory import PoseTrajectory3D
from evo.core.units import Unit

from nav_benchmark.trajectory.models import PoseHealth, Trajectory
from nav_benchmark.trajectory.sync import synchronize_nearest_neighbor


class EvaluationError(ValueError):
    """Exception raised when evaluation preconditions fail or calculation cannot proceed."""

    pass


@dataclass
class EvalConfig:
    association_tolerance_sec: float = 0.1
    alignment_policy: str = "se3"  # "se3" or "none"
    correct_scale: bool = False
    time_offset_search: bool = False
    outlier_rejection: str = "none"
    rpe_delta_m: float = 1.0
    drift_bin_width_m: float = 20.0


@dataclass
class EvaluationDiagnostics:
    source_count: int
    target_count: int
    matched_count: int
    unmatched_source_count: int
    unmatched_target_count: int
    tolerance_sec: float
    first_matched_timestamp: float | None
    last_matched_timestamp: float | None
    overlap_sufficiency: float


@dataclass
class CoverageMetrics:
    total_duration_sec: float
    ok_duration_sec: float
    degraded_duration_sec: float
    lost_duration_sec: float
    invalid_duration_sec: float
    ok_fraction: float
    lost_fraction: float
    invalid_fraction: float


@dataclass
class AlignmentResult:
    R: list[list[float]]
    t: list[float]
    scale: float


@dataclass
class MetricSummary:
    ate_rmse: float
    ate_mean: float
    ate_median: float
    ate_std: float
    ate_min: float
    ate_max: float
    rpe_rmse: float
    rpe_mean: float
    rpe_median: float
    rpe_std: float
    rpe_min: float
    rpe_max: float
    final_drift: float
    cumulative_distance: float


@dataclass
class DriftBinSummary:
    bin_start: float
    bin_end: float
    median_error: float | None
    iqr_error: float | None
    pose_count: int


@dataclass
class ErrorVsTimeRow:
    timestamp: float
    estimated_xyz: list[float]
    aligned_ground_truth_xyz: list[float] | None
    xyz_error: list[float] | None
    error_magnitude: float | None
    health: str
    association_residual: float | None


@dataclass
class ErrorVsDistanceRow:
    cumulative_distance: float
    error_magnitude: float
    health: str
    association_residual: float
    bin_start: float
    bin_end: float


@dataclass
class EvaluationResult:
    status: str
    error_message: str | None
    config: EvalConfig
    diagnostics: EvaluationDiagnostics | None = None
    coverage: CoverageMetrics | None = None
    alignment: AlignmentResult | None = None
    metrics: MetricSummary | None = None
    drift_bins: list[DriftBinSummary] = field(default_factory=list)
    error_vs_time: list[ErrorVsTimeRow] = field(default_factory=list)
    error_vs_distance: list[ErrorVsDistanceRow] = field(default_factory=list)
    aligned_estimate: Trajectory | None = None
    aligned_ground_truth: Trajectory | None = None


def read_project_csv(path: str | Path) -> Trajectory:
    """
    Reads a trajectory CSV file following the project schema:
    timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms
    and returns a Trajectory object.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trajectory file not found: {path}")

    timestamps = []
    positions = []
    orientations = []
    velocities = []
    confidence = []
    health = []
    latency_ms = []
    method = None

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as err:
            raise EvaluationError(f"CSV file is empty: {path}") from err

        # Basic verification of required columns
        required = {"timestamp", "method", "x", "y", "z", "qx", "qy", "qz", "qw"}
        header_set = set(header)
        if not required.issubset(header_set):
            raise EvaluationError(f"Missing required columns in CSV: {required - header_set}")

        indices = {col: header.index(col) for col in header}

        for idx, row in enumerate(reader):
            if not row:
                continue
            if len(row) < len(header):
                raise EvaluationError(f"Row {idx + 2} is malformed or truncated")

            # Extract fields
            ts_str = row[indices["timestamp"]]
            method_str = row[indices["method"]]
            x_str = row[indices["x"]]
            y_str = row[indices["y"]]
            z_str = row[indices["z"]]
            qx_str = row[indices["qx"]]
            qy_str = row[indices["qy"]]
            qz_str = row[indices["qz"]]
            qw_str = row[indices["qw"]]

            try:
                ts = float(ts_str)
                x = float(x_str)
                y = float(y_str)
                z = float(z_str)
                qx = float(qx_str)
                qy = float(qy_str)
                qz = float(qz_str)
                qw = float(qw_str)
            except ValueError as e:
                raise EvaluationError(f"Non-numeric value in row {idx + 2}: {e}") from e

            if not (
                np.isfinite(ts)
                and np.isfinite(x)
                and np.isfinite(y)
                and np.isfinite(z)
                and np.isfinite(qx)
                and np.isfinite(qy)
                and np.isfinite(qz)
                and np.isfinite(qw)
            ):
                raise EvaluationError(f"Non-finite value in row {idx + 2}")

            timestamps.append(ts)
            if method is None:
                method = method_str

            positions.append([x, y, z])
            orientations.append([qx, qy, qz, qw])

            # Optional velocities
            if "vx" in indices and "vy" in indices and "vz" in indices:
                vx_s, vy_s, vz_s = row[indices["vx"]], row[indices["vy"]], row[indices["vz"]]
                if vx_s != "" and vy_s != "" and vz_s != "":
                    try:
                        velocities.append([float(vx_s), float(vy_s), float(vz_s)])
                    except ValueError:
                        velocities.append([0.0, 0.0, 0.0])
                else:
                    velocities.append([0.0, 0.0, 0.0])
            else:
                velocities.append([0.0, 0.0, 0.0])

            # Optional confidence
            if "confidence" in indices:
                conf_s = row[indices["confidence"]]
                if conf_s != "":
                    try:
                        confidence.append(float(conf_s))
                    except ValueError:
                        confidence.append(1.0)
                else:
                    confidence.append(1.0)
            else:
                confidence.append(1.0)

            # Optional health
            if "health" in indices:
                h_val = row[indices["health"]]
                if h_val == "":
                    h_val = "OK"
                health.append(h_val)
            else:
                health.append("OK")

            # Optional latency_ms
            if "latency_ms" in indices:
                lat_s = row[indices["latency_ms"]]
                if lat_s != "":
                    try:
                        latency_ms.append(float(lat_s))
                    except ValueError:
                        latency_ms.append(0.0)
                else:
                    latency_ms.append(0.0)
            else:
                latency_ms.append(0.0)

    if not timestamps:
        raise EvaluationError("No trajectory rows found in CSV")

    ts_arr = np.array(timestamps, dtype=np.float64)
    pos_arr = np.array(positions, dtype=np.float64)
    orient_arr = np.array(orientations, dtype=np.float64)
    vel_arr = np.array(velocities, dtype=np.float64)
    conf_arr = np.array(confidence, dtype=np.float64)
    health_arr = np.array(health, dtype=object)
    lat_arr = np.array(latency_ms, dtype=np.float64)

    # Quaternion validation
    norms = np.linalg.norm(orient_arr, axis=1)
    if np.any(norms == 0.0):
        raise EvaluationError("Zero/degenerate orientation quaternion found")
    orient_arr = orient_arr / norms[:, np.newaxis]

    # Monotonicity check
    if len(ts_arr) > 1 and np.any(np.diff(ts_arr) < 0):
        raise EvaluationError("Timestamps are not strictly monotonic")

    # Health label checks
    valid_states = {h.value for h in PoseHealth}
    for idx, h_val in enumerate(health_arr):
        if h_val not in valid_states:
            raise EvaluationError(f"Invalid health value at index {idx}: {h_val}. Must be one of {valid_states}")

    return Trajectory(
        timestamps=ts_arr,
        method=method or "unknown",
        positions=pos_arr,
        orientations=orient_arr,
        velocities=vel_arr,
        confidence=conf_arr,
        health=health_arr,
        latency_ms=lat_arr,
    )


def evaluate_trajectory(estimate: Trajectory, reference: Trajectory, config: EvalConfig) -> EvaluationResult:
    """
    Evaluates an estimated trajectory against a ground-truth reference trajectory.
    """
    # 1. Validation and input verification
    if len(estimate.timestamps) == 0:
        raise EvaluationError("Estimate trajectory is empty")
    if len(reference.timestamps) == 0:
        raise EvaluationError("Reference trajectory is empty")

    if len(estimate.timestamps) > 1 and np.any(np.diff(estimate.timestamps) < 0):
        raise EvaluationError("Estimate timestamps are not monotonic")
    if len(reference.timestamps) > 1 and np.any(np.diff(reference.timestamps) < 0):
        raise EvaluationError("Reference timestamps are not monotonic")

    if not np.all(np.isfinite(estimate.positions)) or not np.all(np.isfinite(estimate.orientations)):
        raise EvaluationError("Estimate positions/orientations contain non-finite values")
    if not np.all(np.isfinite(reference.positions)) or not np.all(np.isfinite(reference.orientations)):
        raise EvaluationError("Reference positions/orientations contain non-finite values")

    # 2. Coverage Metrics (computed on original estimate trajectory)
    timestamps = estimate.timestamps
    total_duration = float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0

    durations = np.zeros(len(timestamps))
    if len(timestamps) > 1:
        durations[:-1] = np.diff(timestamps)
        durations[-1] = durations[-2] if len(durations) > 2 else 0.0

    h_arr = estimate.health if estimate.health is not None else np.array(["OK"] * len(timestamps), dtype=object)

    ok_dur = float(np.sum(durations[h_arr == "OK"]))
    deg_dur = float(np.sum(durations[h_arr == "DEGRADED"]))
    lost_dur = float(np.sum(durations[h_arr == "LOST"]))
    inv_dur = float(np.sum(durations[h_arr == "INVALID"]))

    cov = CoverageMetrics(
        total_duration_sec=total_duration,
        ok_duration_sec=ok_dur,
        degraded_duration_sec=deg_dur,
        lost_duration_sec=lost_dur,
        invalid_duration_sec=inv_dur,
        ok_fraction=ok_dur / total_duration if total_duration > 0 else 0.0,
        lost_fraction=lost_dur / total_duration if total_duration > 0 else 0.0,
        invalid_fraction=inv_dur / total_duration if total_duration > 0 else 0.0,
    )

    # 3. Filter estimate to only OK/DEGRADED poses
    ok_deg_mask = np.isin(h_arr, ["OK", "DEGRADED"])
    if np.sum(ok_deg_mask) < 3:
        raise EvaluationError(
            "Insufficient OK/DEGRADED poses in estimate trajectory (minimum 3 required for SE(3) alignment)"
        )

    est_ts_filt = estimate.timestamps[ok_deg_mask]

    # 4. Synchronize filtered estimate timestamps to reference timestamps
    try:
        matched_est_filt_idx, matched_ref_idx, sync_diag = synchronize_nearest_neighbor(
            est_ts_filt, reference.timestamps, config.association_tolerance_sec
        )
    except Exception as e:
        raise EvaluationError(f"Timestamp synchronization failed: {e}") from e

    # Map matched_est_filt_idx back to original estimate indices
    ok_deg_orig_indices = np.where(ok_deg_mask)[0]
    matched_est_orig_idx = ok_deg_orig_indices[matched_est_filt_idx]

    matched_count = len(matched_est_orig_idx)
    if matched_count < 3:
        raise EvaluationError(
            "Insufficient matched poses between estimate and reference after synchronization (minimum 3 required for SE(3) alignment)"
        )

    # 5. Extract matched positions/orientations and construct evo trajectory objects
    matched_ref_positions = reference.positions[matched_ref_idx]
    matched_ref_orientations_xyzw = reference.orientations[matched_ref_idx]
    matched_ref_orientations_wxyz = matched_ref_orientations_xyzw[:, [3, 0, 1, 2]]
    matched_ref_timestamps = reference.timestamps[matched_ref_idx]

    matched_ref_pose_traj = PoseTrajectory3D(
        positions_xyz=matched_ref_positions,
        orientations_quat_wxyz=matched_ref_orientations_wxyz,
        timestamps=matched_ref_timestamps,
    )

    matched_est_positions = estimate.positions[matched_est_orig_idx]
    matched_est_orientations_xyzw = estimate.orientations[matched_est_orig_idx]
    matched_est_orientations_wxyz = matched_est_orientations_xyzw[:, [3, 0, 1, 2]]
    matched_est_timestamps = estimate.timestamps[matched_est_orig_idx]

    matched_est_pose_traj = PoseTrajectory3D(
        positions_xyz=matched_est_positions,
        orientations_quat_wxyz=matched_est_orientations_wxyz,
        timestamps=matched_est_timestamps,
    )

    # 6. SE(3) Trajectory Alignment
    if config.alignment_policy == "se3":
        try:
            R_align, t_align, scale_align = matched_est_pose_traj.align(
                matched_ref_pose_traj, correct_scale=config.correct_scale
            )
        except Exception as e:
            raise EvaluationError(f"Global SE(3) alignment failed: {e}") from e

        # Construct transformation matrix
        T = np.identity(4)
        T[:3, :3] = scale_align * R_align
        T[:3, 3] = t_align

        # Transform full estimated trajectory (positions and orientations)
        all_est_wxyz = estimate.orientations[:, [3, 0, 1, 2]]
        full_est_traj = PoseTrajectory3D(
            positions_xyz=estimate.positions,
            orientations_quat_wxyz=all_est_wxyz,
            timestamps=estimate.timestamps,
        )
        full_est_traj.transform(T)

        aligned_positions = full_est_traj.positions_xyz
        aligned_orientations_xyzw = full_est_traj.orientations_quat_wxyz[:, [1, 2, 3, 0]]
        align_result = AlignmentResult(
            R=R_align.tolist(),
            t=t_align.tolist(),
            scale=float(scale_align),
        )
    else:
        aligned_positions = estimate.positions.copy()
        aligned_orientations_xyzw = estimate.orientations.copy()
        align_result = AlignmentResult(
            R=np.identity(3).tolist(),
            t=[0.0, 0.0, 0.0],
            scale=1.0,
        )

    # Re-extract matched estimate positions after alignment
    matched_est_positions_aligned = aligned_positions[matched_est_orig_idx]
    matched_est_orientations_aligned_wxyz = aligned_orientations_xyzw[matched_est_orig_idx][:, [3, 0, 1, 2]]

    # 7. Compute ATE
    ate_errors = np.linalg.norm(matched_est_positions_aligned - matched_ref_positions, axis=1)
    ate_rmse = float(np.sqrt(np.mean(ate_errors**2)))
    ate_mean = float(np.mean(ate_errors))
    ate_median = float(np.median(ate_errors))
    ate_std = float(np.std(ate_errors))
    ate_min = float(np.min(ate_errors))
    ate_max = float(np.max(ate_errors))

    # 8. Compute RPE
    traj_ref_matched_eval = PoseTrajectory3D(
        positions_xyz=matched_ref_positions,
        orientations_quat_wxyz=matched_ref_orientations_wxyz,
        timestamps=matched_ref_timestamps,
    )
    traj_est_matched_eval_aligned = PoseTrajectory3D(
        positions_xyz=matched_est_positions_aligned,
        orientations_quat_wxyz=matched_est_orientations_aligned_wxyz,
        timestamps=matched_est_timestamps,
    )

    rpe_metric = evo_metrics.RPE(
        evo_metrics.PoseRelation.translation_part,
        delta=config.rpe_delta_m,
        delta_unit=Unit.meters,
        all_pairs=True,
    )

    try:
        rpe_metric.process_data((traj_ref_matched_eval, traj_est_matched_eval_aligned))
        rpe_stats = rpe_metric.get_all_statistics()
        rpe_rmse = float(rpe_stats.get("rmse", 0.0))
        rpe_mean = float(rpe_stats.get("mean", 0.0))
        rpe_median = float(rpe_stats.get("median", 0.0))
        rpe_std = float(rpe_stats.get("std", 0.0))
        rpe_min = float(rpe_stats.get("min", 0.0))
        rpe_max = float(rpe_stats.get("max", 0.0))
    except Exception:
        # Fallback to nan / 0.0 if RPE cannot be computed due to short distances
        rpe_rmse = float("nan")
        rpe_mean = float("nan")
        rpe_median = float("nan")
        rpe_std = float("nan")
        rpe_min = float("nan")
        rpe_max = float("nan")

    # 9. Compute Cumulative Distance on OK/DEGRADED estimate poses
    diffs = np.diff(estimate.positions[ok_deg_mask], axis=0)
    dists = np.linalg.norm(diffs, axis=1)
    cum_dists_ok_deg = np.zeros(np.sum(ok_deg_mask))
    cum_dists_ok_deg[1:] = np.cumsum(dists)

    cumulative_distance = float(cum_dists_ok_deg[-1]) if len(cum_dists_ok_deg) > 0 else 0.0

    # Extract cumulative distances corresponding to matched poses
    cum_dists_matched = cum_dists_ok_deg[matched_est_filt_idx]

    # 10. Final Drift
    final_drift = float(ate_errors[-1]) if len(ate_errors) > 0 else 0.0

    metric_summary = MetricSummary(
        ate_rmse=ate_rmse,
        ate_mean=ate_mean,
        ate_median=ate_median,
        ate_std=ate_std,
        ate_min=ate_min,
        ate_max=ate_max,
        rpe_rmse=rpe_rmse,
        rpe_mean=rpe_mean,
        rpe_median=rpe_median,
        rpe_std=rpe_std,
        rpe_min=rpe_min,
        rpe_max=rpe_max,
        final_drift=final_drift,
        cumulative_distance=cumulative_distance,
    )

    # 11. Compile ErrorVsTimeRow
    error_vs_time = []
    # Map matched_est_orig_idx to index in matched arrays
    orig_idx_to_matched_k = {orig_idx: k for k, orig_idx in enumerate(matched_est_orig_idx)}

    for i in range(len(estimate.timestamps)):
        h_str = str(h_arr[i])
        ts = float(estimate.timestamps[i])
        est_xyz = aligned_positions[i].tolist()

        if i in orig_idx_to_matched_k:
            k = orig_idx_to_matched_k[i]
            ref_xyz = reference.positions[matched_ref_idx[k]].tolist()
            err_xyz = (aligned_positions[i] - reference.positions[matched_ref_idx[k]]).tolist()
            err_mag = float(ate_errors[k])
            res_val = float(abs(ts - reference.timestamps[matched_ref_idx[k]]))
        else:
            ref_xyz = None
            err_xyz = None
            err_mag = None
            res_val = None

        error_vs_time.append(
            ErrorVsTimeRow(
                timestamp=ts,
                estimated_xyz=est_xyz,
                aligned_ground_truth_xyz=ref_xyz,
                xyz_error=err_xyz,
                error_magnitude=err_mag,
                health=h_str,
                association_residual=res_val,
            )
        )

    # 12. Compile ErrorVsDistanceRow and DriftBinSummary
    error_vs_distance = []
    for k in range(matched_count):
        dist = float(cum_dists_matched[k])
        err_mag = float(ate_errors[k])
        orig_i = matched_est_orig_idx[k]
        h_str = str(h_arr[orig_i])
        res_val = float(abs(estimate.timestamps[orig_i] - reference.timestamps[matched_ref_idx[k]]))
        bin_start = float((dist // config.drift_bin_width_m) * config.drift_bin_width_m)
        bin_end = bin_start + config.drift_bin_width_m

        error_vs_distance.append(
            ErrorVsDistanceRow(
                cumulative_distance=dist,
                error_magnitude=err_mag,
                health=h_str,
                association_residual=res_val,
                bin_start=bin_start,
                bin_end=bin_end,
            )
        )

    # Drift Bin Summaries
    drift_bins = []
    if matched_count > 0:
        max_matched_dist = cum_dists_matched[-1]
        num_bins = int(np.ceil(max_matched_dist / config.drift_bin_width_m))
        if num_bins == 0:
            num_bins = 1

        for i in range(num_bins):
            b_start = float(i * config.drift_bin_width_m)
            b_end = b_start + config.drift_bin_width_m

            if i == num_bins - 1:
                in_bin = (cum_dists_matched >= b_start) & (cum_dists_matched <= b_end)
            else:
                in_bin = (cum_dists_matched >= b_start) & (cum_dists_matched < b_end)

            pose_count_bin = int(np.sum(in_bin))
            if pose_count_bin > 0:
                bin_errors = ate_errors[in_bin]
                median_err = float(np.median(bin_errors))
                q75, q25 = np.percentile(bin_errors, [75, 25])
                iqr_err = float(q75 - q25)
            else:
                median_err = None
                iqr_err = None

            drift_bins.append(
                DriftBinSummary(
                    bin_start=b_start,
                    bin_end=b_end,
                    median_error=median_err,
                    iqr_error=iqr_err,
                    pose_count=pose_count_bin,
                )
            )

    eval_diag = EvaluationDiagnostics(
        source_count=int(sync_diag.source_count),
        target_count=int(sync_diag.target_count),
        matched_count=int(sync_diag.matched_count),
        unmatched_source_count=int(sync_diag.unmatched_source_count),
        unmatched_target_count=int(sync_diag.unmatched_target_count),
        tolerance_sec=float(sync_diag.tolerance_sec),
        first_matched_timestamp=float(sync_diag.first_matched_timestamp)
        if sync_diag.first_matched_timestamp is not None
        else None,
        last_matched_timestamp=float(sync_diag.last_matched_timestamp)
        if sync_diag.last_matched_timestamp is not None
        else None,
        overlap_sufficiency=float(sync_diag.overlap_sufficiency),
    )

    aligned_est_trajectory = Trajectory(
        timestamps=estimate.timestamps,
        method=estimate.method,
        positions=aligned_positions,
        orientations=aligned_orientations_xyzw,
        velocities=estimate.velocities,
        confidence=estimate.confidence,
        health=estimate.health,
        latency_ms=estimate.latency_ms,
    )

    aligned_gt_trajectory = Trajectory(
        timestamps=matched_ref_timestamps,
        method="ground_truth",
        positions=matched_ref_positions,
        orientations=matched_ref_orientations_xyzw,
        velocities=reference.velocities[matched_ref_idx] if reference.velocities is not None else None,
        confidence=reference.confidence[matched_ref_idx] if reference.confidence is not None else None,
        health=np.array([PoseHealth.OK] * matched_count, dtype=object),
        latency_ms=reference.latency_ms[matched_ref_idx] if reference.latency_ms is not None else None,
    )

    return EvaluationResult(
        status="OK",
        error_message=None,
        config=config,
        diagnostics=eval_diag,
        coverage=cov,
        alignment=align_result,
        metrics=metric_summary,
        drift_bins=drift_bins,
        error_vs_time=error_vs_time,
        error_vs_distance=error_vs_distance,
        aligned_estimate=aligned_est_trajectory,
        aligned_ground_truth=aligned_gt_trajectory,
    )


def make_json_serializable(val: Any) -> Any:
    """Helper to convert objects/numpy types to standard JSON-compatible formats."""
    if isinstance(val, dict):
        return {k: make_json_serializable(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [make_json_serializable(v) for v in val]
    elif isinstance(val, float):
        if not np.isfinite(val):
            return None
        return val
    elif isinstance(val, (np.floating, np.integer)):
        if not np.isfinite(val):
            return None
        return float(val) if isinstance(val, np.floating) else int(val)
    elif isinstance(val, np.ndarray):
        return make_json_serializable(val.tolist())
    elif hasattr(val, "__dataclass_fields__"):
        return make_json_serializable(asdict(val))
    return val


def export_metrics_json(result: EvaluationResult, path: str | Path) -> None:
    """Exports metrics to a JSON file."""
    path = Path(path)
    serializable = make_json_serializable(result)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def export_error_vs_time_csv(result: EvaluationResult, path: str | Path) -> None:
    """Exports error vs time series to CSV."""
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
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
            ]
        )
        for row in result.error_vs_time:
            # Handle optionals
            gt_x, gt_y, gt_z = row.aligned_ground_truth_xyz if row.aligned_ground_truth_xyz else ("", "", "")
            err_x, err_y, err_z = row.xyz_error if row.xyz_error else ("", "", "")
            err_mag = f"{row.error_magnitude:.9f}" if row.error_magnitude is not None else ""
            res_val = f"{row.association_residual:.9f}" if row.association_residual is not None else ""

            writer.writerow(
                [
                    f"{row.timestamp:.9f}",
                    f"{row.estimated_xyz[0]:.9f}",
                    f"{row.estimated_xyz[1]:.9f}",
                    f"{row.estimated_xyz[2]:.9f}",
                    f"{gt_x:.9f}" if isinstance(gt_x, float) else gt_x,
                    f"{gt_y:.9f}" if isinstance(gt_y, float) else gt_y,
                    f"{gt_z:.9f}" if isinstance(gt_z, float) else gt_z,
                    f"{err_x:.9f}" if isinstance(err_x, float) else err_x,
                    f"{err_y:.9f}" if isinstance(err_y, float) else err_y,
                    f"{err_z:.9f}" if isinstance(err_z, float) else err_z,
                    err_mag,
                    row.health,
                    res_val,
                ]
            )


def export_error_vs_distance_csv(result: EvaluationResult, path: str | Path) -> None:
    """Exports error vs distance series to CSV."""
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "cumulative_distance",
                "error_magnitude",
                "health",
                "association_residual",
                "bin_start",
                "bin_end",
            ]
        )
        for row in result.error_vs_distance:
            writer.writerow(
                [
                    f"{row.cumulative_distance:.9f}",
                    f"{row.error_magnitude:.9f}",
                    row.health,
                    f"{row.association_residual:.9f}",
                    f"{row.bin_start:.2f}",
                    f"{row.bin_end:.2f}",
                ]
            )
