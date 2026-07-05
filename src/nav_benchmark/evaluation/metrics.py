import csv
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from evo.core import metrics as evo_metrics
from evo.core.trajectory import PoseTrajectory3D
from evo.core.units import Unit
from scipy.spatial.transform import Rotation

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
    distance_markers_m: tuple[float, ...] = (20.0, 50.0, 100.0, 200.0)


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
class RuntimeMetrics:
    update_count: int
    duration_sec: float
    odometry_frequency_hz: float
    latency_mean_ms: float | None
    latency_median_ms: float | None
    latency_p95_ms: float | None
    latency_max_ms: float | None
    total_processing_time_sec: float | None = None
    real_time_factor: float | None = None


@dataclass
class FailureMetrics:
    ok_pose_count: int
    degraded_pose_count: int
    lost_pose_count: int
    invalid_pose_count: int
    failed_frame_count: int
    failed_frame_fraction: float
    failed_window_count: int
    failed_duration_sec: float


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
    drift_percent: float | None = None
    heading_error_mean_deg: float | None = None
    heading_error_p95_deg: float | None = None
    error_at_distance_m: dict[str, float | None] = field(default_factory=dict)


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
    runtime: RuntimeMetrics | None = None
    failures: FailureMetrics | None = None
    alignment: AlignmentResult | None = None
    metrics: MetricSummary | None = None
    drift_bins: list[DriftBinSummary] = field(default_factory=list)
    error_vs_time: list[ErrorVsTimeRow] = field(default_factory=list)
    error_vs_distance: list[ErrorVsDistanceRow] = field(default_factory=list)
    aligned_estimate: Trajectory | None = None
    aligned_ground_truth: Trajectory | None = None


_REQUIRED_TRAJECTORY_COLUMNS = {"timestamp", "method", "x", "y", "z", "qx", "qy", "qz", "qw"}


def _read_csv_header(reader: Iterator[list[str]], path: Path) -> list[str]:
    try:
        return next(reader)
    except StopIteration as err:
        raise EvaluationError(f"CSV file is empty: {path}") from err


def _csv_column_indices(header: list[str]) -> dict[str, int]:
    header_set = set(header)
    if not _REQUIRED_TRAJECTORY_COLUMNS.issubset(header_set):
        missing = _REQUIRED_TRAJECTORY_COLUMNS - header_set
        raise EvaluationError(f"Missing required columns in CSV: {missing}")
    return {col: header.index(col) for col in header}


def _required_float(row: list[str], indices: dict[str, int], column: str, row_number: int) -> float:
    try:
        return float(row[indices[column]])
    except ValueError as err:
        raise EvaluationError(f"Non-numeric value in row {row_number}: {err}") from err


def _parse_required_csv_pose(
    row: list[str], indices: dict[str, int], row_number: int
) -> tuple[float, str, list[float], list[float]]:
    values = {
        column: _required_float(row, indices, column, row_number)
        for column in ("timestamp", "x", "y", "z", "qx", "qy", "qz", "qw")
    }
    if not all(np.isfinite(value) for value in values.values()):
        raise EvaluationError(f"Non-finite value in row {row_number}")

    position = [values["x"], values["y"], values["z"]]
    orientation = [values["qx"], values["qy"], values["qz"], values["qw"]]
    return values["timestamp"], row[indices["method"]], position, orientation


def _optional_float(row: list[str], indices: dict[str, int], column: str, default: float) -> float:
    if column not in indices:
        return default
    value = row[indices[column]]
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _zero_velocity() -> list[float]:
    return [0.0, 0.0, 0.0]


def _has_velocity_columns(indices: dict[str, int]) -> bool:
    return all(column in indices for column in ("vx", "vy", "vz"))


def _float_vector_or_default(values: list[str], default: list[float]) -> list[float]:
    if "" in values:
        return default
    try:
        return [float(value) for value in values]
    except ValueError:
        return default


def _optional_velocity(row: list[str], indices: dict[str, int]) -> list[float]:
    columns = ("vx", "vy", "vz")
    if not _has_velocity_columns(indices):
        return _zero_velocity()
    values = [row[indices[column]] for column in columns]
    return _float_vector_or_default(values, _zero_velocity())


def _optional_health(row: list[str], indices: dict[str, int]) -> str:
    if "health" not in indices:
        return PoseHealth.OK.value
    return row[indices["health"]] or PoseHealth.OK.value


def _normalize_csv_orientations(orientations: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(orientations, axis=1)
    if np.any(norms == 0.0):
        raise EvaluationError("Zero/degenerate orientation quaternion found")
    return orientations / norms[:, np.newaxis]


def _validate_csv_timestamps(timestamps: np.ndarray) -> None:
    if len(timestamps) > 1 and np.any(np.diff(timestamps) < 0):
        raise EvaluationError("Timestamps are not strictly monotonic")


def _validate_csv_health(health: np.ndarray) -> None:
    valid_states = {state.value for state in PoseHealth}
    for idx, value in enumerate(health):
        if value not in valid_states:
            raise EvaluationError(f"Invalid health value at index {idx}: {value}. Must be one of {valid_states}")


def _append_csv_trajectory_row(
    row: list[str],
    row_number: int,
    indices: dict[str, int],
    columns: dict[str, list],
) -> None:
    if not row:
        return
    if len(row) < len(indices):
        raise EvaluationError(f"Row {row_number} is malformed or truncated")

    ts, method_str, position, orientation = _parse_required_csv_pose(row, indices, row_number)
    columns["timestamps"].append(ts)
    columns["method"].append(method_str)
    columns["positions"].append(position)
    columns["orientations"].append(orientation)
    columns["velocities"].append(_optional_velocity(row, indices))
    columns["confidence"].append(_optional_float(row, indices, "confidence", 1.0))
    columns["health"].append(_optional_health(row, indices))
    columns["latency_ms"].append(_optional_float(row, indices, "latency_ms", 0.0))


def read_project_csv(path: str | Path) -> Trajectory:
    """
    Reads a trajectory CSV file following the project schema:
    timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms
    and returns a Trajectory object.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trajectory file not found: {path}")

    columns: dict[str, list] = {
        "timestamps": [],
        "method": [],
        "positions": [],
        "orientations": [],
        "velocities": [],
        "confidence": [],
        "health": [],
        "latency_ms": [],
    }

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        indices = _csv_column_indices(_read_csv_header(reader, path))

        for idx, row in enumerate(reader):
            _append_csv_trajectory_row(row, idx + 2, indices, columns)

    if not columns["timestamps"]:
        raise EvaluationError("No trajectory rows found in CSV")

    ts_arr = np.array(columns["timestamps"], dtype=np.float64)
    pos_arr = np.array(columns["positions"], dtype=np.float64)
    orient_arr = np.array(columns["orientations"], dtype=np.float64)
    vel_arr = np.array(columns["velocities"], dtype=np.float64)
    conf_arr = np.array(columns["confidence"], dtype=np.float64)
    health_arr = np.array(columns["health"], dtype=object)
    lat_arr = np.array(columns["latency_ms"], dtype=np.float64)

    orient_arr = _normalize_csv_orientations(orient_arr)
    _validate_csv_timestamps(ts_arr)
    _validate_csv_health(health_arr)

    return Trajectory(
        timestamps=ts_arr,
        method=columns["method"][0] if columns["method"] else "unknown",
        positions=pos_arr,
        orientations=orient_arr,
        velocities=vel_arr,
        confidence=conf_arr,
        health=health_arr,
        latency_ms=lat_arr,
    )


def _health_labels(health: np.ndarray | None, count: int) -> np.ndarray:
    if health is None:
        return np.array([PoseHealth.OK.value] * count, dtype=object)
    return np.array([str(value) for value in health], dtype=object)


def _sample_durations(timestamps: np.ndarray) -> np.ndarray:
    durations = np.zeros(len(timestamps), dtype=np.float64)
    if len(timestamps) > 1:
        durations[:-1] = np.diff(timestamps)
        durations[-1] = durations[-2] if len(durations) > 2 else 0.0
    return durations


def _finite_latencies(latency_ms: np.ndarray | None) -> np.ndarray:
    if latency_ms is None:
        return np.array([], dtype=np.float64)
    latencies = np.asarray(latency_ms, dtype=np.float64)
    return latencies[np.isfinite(latencies)]


def _latency_statistics(finite_latency: np.ndarray) -> dict[str, float | None]:
    if finite_latency.size == 0:
        return {"mean": None, "median": None, "p95": None, "max": None}
    return {
        "mean": float(np.mean(finite_latency)),
        "median": float(np.median(finite_latency)),
        "p95": float(np.percentile(finite_latency, 95)),
        "max": float(np.max(finite_latency)),
    }


def _real_time_factor(duration_sec: float, total_processing_time_sec: float | None) -> float | None:
    if total_processing_time_sec is None or total_processing_time_sec <= 0.0 or duration_sec <= 0.0:
        return None
    # > 1.0 means the method processed the sequence faster than real time.
    return duration_sec / total_processing_time_sec


def _compute_runtime_metrics(timestamps: np.ndarray, latency_ms: np.ndarray | None) -> RuntimeMetrics:
    duration_sec = float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0
    odometry_frequency_hz = float((len(timestamps) - 1) / duration_sec) if duration_sec > 0.0 else 0.0

    finite_latency = _finite_latencies(latency_ms)
    latency_stats = _latency_statistics(finite_latency)
    total_processing_time_sec = float(np.sum(finite_latency) / 1000.0) if finite_latency.size else None

    return RuntimeMetrics(
        update_count=len(timestamps),
        duration_sec=duration_sec,
        odometry_frequency_hz=odometry_frequency_hz,
        latency_mean_ms=latency_stats["mean"],
        latency_median_ms=latency_stats["median"],
        latency_p95_ms=latency_stats["p95"],
        latency_max_ms=latency_stats["max"],
        total_processing_time_sec=total_processing_time_sec,
        real_time_factor=_real_time_factor(duration_sec, total_processing_time_sec),
    )


def _compute_failure_metrics(health_labels: np.ndarray, durations: np.ndarray) -> FailureMetrics:
    ok_count = int(np.sum(health_labels == PoseHealth.OK.value))
    degraded_count = int(np.sum(health_labels == PoseHealth.DEGRADED.value))
    lost_count = int(np.sum(health_labels == PoseHealth.LOST.value))
    invalid_count = int(np.sum(health_labels == PoseHealth.INVALID.value))

    failed_mask = np.isin(health_labels, [PoseHealth.LOST.value, PoseHealth.INVALID.value])
    if failed_mask.size == 0:
        failed_window_count = 0
    else:
        failed_window_starts = failed_mask & np.concatenate(([True], ~failed_mask[:-1]))
        failed_window_count = int(np.sum(failed_window_starts))

    failed_frame_count = int(np.sum(failed_mask))
    return FailureMetrics(
        ok_pose_count=ok_count,
        degraded_pose_count=degraded_count,
        lost_pose_count=lost_count,
        invalid_pose_count=invalid_count,
        failed_frame_count=failed_frame_count,
        failed_frame_fraction=failed_frame_count / len(health_labels) if len(health_labels) > 0 else 0.0,
        failed_window_count=failed_window_count,
        failed_duration_sec=float(np.sum(durations[failed_mask])) if durations.size else 0.0,
    )


@dataclass
class _EvaluationPreparation:
    durations: np.ndarray
    health_labels: np.ndarray
    coverage: CoverageMetrics
    runtime: RuntimeMetrics
    failures: FailureMetrics
    eligible_mask: np.ndarray


@dataclass
class _MatchedTrajectoryData:
    matched_est_filt_idx: np.ndarray
    matched_est_orig_idx: np.ndarray
    matched_ref_idx: np.ndarray
    sync_diag: Any
    ref_positions: np.ndarray
    ref_orientations_xyzw: np.ndarray
    ref_orientations_wxyz: np.ndarray
    ref_timestamps: np.ndarray
    est_timestamps: np.ndarray


@dataclass
class _AlignmentData:
    positions: np.ndarray
    orientations_xyzw: np.ndarray
    result: AlignmentResult


def _require_nonempty_trajectory(name: str, trajectory: Trajectory) -> None:
    if len(trajectory.timestamps) == 0:
        raise EvaluationError(f"{name} trajectory is empty")


def _require_monotonic_trajectory_timestamps(name: str, timestamps: np.ndarray) -> None:
    if len(timestamps) > 1 and np.any(np.diff(timestamps) < 0):
        raise EvaluationError(f"{name} timestamps are not monotonic")


def _require_finite_trajectory_pose_arrays(name: str, trajectory: Trajectory) -> None:
    positions_are_finite = np.all(np.isfinite(trajectory.positions))
    orientations_are_finite = np.all(np.isfinite(trajectory.orientations))
    if not positions_are_finite or not orientations_are_finite:
        raise EvaluationError(f"{name} positions/orientations contain non-finite values")


def _validate_evaluation_trajectory(name: str, trajectory: Trajectory) -> None:
    _require_nonempty_trajectory(name, trajectory)
    _require_monotonic_trajectory_timestamps(name, trajectory.timestamps)
    _require_finite_trajectory_pose_arrays(name, trajectory)


def _coverage_metrics_from_estimate(
    timestamps: np.ndarray, health_labels: np.ndarray, durations: np.ndarray
) -> CoverageMetrics:
    total_duration = float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0
    ok_dur = float(np.sum(durations[health_labels == PoseHealth.OK.value]))
    deg_dur = float(np.sum(durations[health_labels == PoseHealth.DEGRADED.value]))
    lost_dur = float(np.sum(durations[health_labels == PoseHealth.LOST.value]))
    inv_dur = float(np.sum(durations[health_labels == PoseHealth.INVALID.value]))
    return CoverageMetrics(
        total_duration_sec=total_duration,
        ok_duration_sec=ok_dur,
        degraded_duration_sec=deg_dur,
        lost_duration_sec=lost_dur,
        invalid_duration_sec=inv_dur,
        ok_fraction=ok_dur / total_duration if total_duration > 0 else 0.0,
        lost_fraction=lost_dur / total_duration if total_duration > 0 else 0.0,
        invalid_fraction=inv_dur / total_duration if total_duration > 0 else 0.0,
    )


def _eligible_pose_mask(health_labels: np.ndarray) -> np.ndarray:
    mask = np.isin(health_labels, [PoseHealth.OK.value, PoseHealth.DEGRADED.value])
    if int(np.sum(mask)) < 3:
        raise EvaluationError(
            "Insufficient OK/DEGRADED poses in estimate trajectory (minimum 3 required for SE(3) alignment)"
        )
    return mask


def _prepare_evaluation(estimate: Trajectory) -> _EvaluationPreparation:
    timestamps = estimate.timestamps
    durations = _sample_durations(timestamps)
    health_labels = _health_labels(estimate.health, len(timestamps))
    return _EvaluationPreparation(
        durations=durations,
        health_labels=health_labels,
        coverage=_coverage_metrics_from_estimate(timestamps, health_labels, durations),
        runtime=_compute_runtime_metrics(timestamps, estimate.latency_ms),
        failures=_compute_failure_metrics(health_labels, durations),
        eligible_mask=_eligible_pose_mask(health_labels),
    )


def _match_trajectories(
    estimate: Trajectory, reference: Trajectory, config: EvalConfig, eligible_mask: np.ndarray
) -> _MatchedTrajectoryData:
    est_ts_filt = estimate.timestamps[eligible_mask]
    try:
        matched_est_filt_idx, matched_ref_idx, sync_diag = synchronize_nearest_neighbor(
            est_ts_filt, reference.timestamps, config.association_tolerance_sec
        )
    except Exception as e:
        raise EvaluationError(f"Timestamp synchronization failed: {e}") from e

    # Map matched_est_filt_idx back to original estimate indices
    ok_deg_orig_indices = np.where(eligible_mask)[0]
    matched_est_orig_idx = ok_deg_orig_indices[matched_est_filt_idx]

    matched_count = len(matched_est_orig_idx)
    if matched_count < 3:
        raise EvaluationError(
            "Insufficient matched poses between estimate and reference after synchronization (minimum 3 required for SE(3) alignment)"
        )

    matched_ref_positions = reference.positions[matched_ref_idx]
    matched_ref_orientations_xyzw = reference.orientations[matched_ref_idx]
    matched_ref_orientations_wxyz = matched_ref_orientations_xyzw[:, [3, 0, 1, 2]]
    matched_ref_timestamps = reference.timestamps[matched_ref_idx]

    return _MatchedTrajectoryData(
        matched_est_filt_idx=matched_est_filt_idx,
        matched_est_orig_idx=matched_est_orig_idx,
        matched_ref_idx=matched_ref_idx,
        sync_diag=sync_diag,
        ref_positions=matched_ref_positions,
        ref_orientations_xyzw=matched_ref_orientations_xyzw,
        ref_orientations_wxyz=matched_ref_orientations_wxyz,
        ref_timestamps=matched_ref_timestamps,
        est_timestamps=estimate.timestamps[matched_est_orig_idx],
    )


def _pose_trajectory_from_xyzw(positions: np.ndarray, orientations_xyzw: np.ndarray, timestamps: np.ndarray):
    return PoseTrajectory3D(
        positions_xyz=positions,
        orientations_quat_wxyz=orientations_xyzw[:, [3, 0, 1, 2]],
        timestamps=timestamps,
    )


def _align_estimate(estimate: Trajectory, matched: _MatchedTrajectoryData, config: EvalConfig) -> _AlignmentData:
    if config.alignment_policy == "se3":
        matched_ref_pose_traj = PoseTrajectory3D(
            positions_xyz=matched.ref_positions,
            orientations_quat_wxyz=matched.ref_orientations_wxyz,
            timestamps=matched.ref_timestamps,
        )
        matched_est_pose_traj = _pose_trajectory_from_xyzw(
            estimate.positions[matched.matched_est_orig_idx],
            estimate.orientations[matched.matched_est_orig_idx],
            matched.est_timestamps,
        )
        try:
            R_align, t_align, scale_align = matched_est_pose_traj.align(
                matched_ref_pose_traj, correct_scale=config.correct_scale
            )
        except Exception as e:
            raise EvaluationError(f"Global SE(3) alignment failed: {e}") from e

        T = np.identity(4)
        T[:3, :3] = scale_align * R_align
        T[:3, 3] = t_align

        full_est_traj = _pose_trajectory_from_xyzw(estimate.positions, estimate.orientations, estimate.timestamps)
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
    return _AlignmentData(aligned_positions, aligned_orientations_xyzw, align_result)


def _rpe_statistics(
    ref_positions: np.ndarray,
    ref_orientations_wxyz: np.ndarray,
    ref_timestamps: np.ndarray,
    est_positions: np.ndarray,
    est_orientations_wxyz: np.ndarray,
    est_timestamps: np.ndarray,
    config: EvalConfig,
) -> dict[str, float]:
    traj_ref_matched_eval = PoseTrajectory3D(
        positions_xyz=ref_positions,
        orientations_quat_wxyz=ref_orientations_wxyz,
        timestamps=ref_timestamps,
    )
    traj_est_matched_eval_aligned = PoseTrajectory3D(
        positions_xyz=est_positions,
        orientations_quat_wxyz=est_orientations_wxyz,
        timestamps=est_timestamps,
    )

    rpe_metric = evo_metrics.RPE(
        evo_metrics.PoseRelation.translation_part,
        delta=config.rpe_delta_m,
        delta_unit=Unit.meters,
        all_pairs=True,
    )

    try:
        rpe_metric.process_data((traj_ref_matched_eval, traj_est_matched_eval_aligned))
        stats = rpe_metric.get_all_statistics()
        return {name: float(stats.get(name, 0.0)) for name in ("rmse", "mean", "median", "std", "min", "max")}
    except Exception:
        return {name: float("nan") for name in ("rmse", "mean", "median", "std", "min", "max")}


def _drift_percent(final_drift: float, cumulative_distance: float) -> float | None:
    if cumulative_distance <= 0.0:
        return None
    return final_drift / cumulative_distance * 100.0


def _yaw_deg_from_xyzw(orientations_xyzw: np.ndarray) -> np.ndarray:
    return np.degrees(Rotation.from_quat(orientations_xyzw).as_euler("zyx")[:, 0])


def _heading_error_stats_deg(
    est_orientations_xyzw: np.ndarray, ref_orientations_xyzw: np.ndarray
) -> tuple[float | None, float | None]:
    """Mean and p95 absolute yaw difference in degrees, wrapped to [-180, 180]."""
    if len(est_orientations_xyzw) == 0:
        return None, None
    diff = _yaw_deg_from_xyzw(est_orientations_xyzw) - _yaw_deg_from_xyzw(ref_orientations_xyzw)
    wrapped = (diff + 180.0) % 360.0 - 180.0
    errors = np.abs(wrapped)
    return float(np.mean(errors)), float(np.percentile(errors, 95))


def _error_at_distance_markers(
    ate_errors: np.ndarray, cum_dists_matched: np.ndarray, markers: tuple[float, ...]
) -> dict[str, float | None]:
    """Error magnitude at the first matched pose reaching each travelled-distance marker."""
    result: dict[str, float | None] = {}
    for marker in markers:
        reached = cum_dists_matched >= marker
        if np.any(reached):
            result[f"{marker:g}"] = float(ate_errors[int(np.argmax(reached))])
        else:
            result[f"{marker:g}"] = None
    return result


def _metric_summary(
    matched: _MatchedTrajectoryData, alignment: _AlignmentData, eligible_positions: np.ndarray, config: EvalConfig
) -> tuple[MetricSummary, np.ndarray, np.ndarray]:
    matched_est_positions_aligned = alignment.positions[matched.matched_est_orig_idx]
    matched_est_orientations_aligned_wxyz = alignment.orientations_xyzw[matched.matched_est_orig_idx][:, [3, 0, 1, 2]]
    ate_errors = np.linalg.norm(matched_est_positions_aligned - matched.ref_positions, axis=1)
    ate_rmse = float(np.sqrt(np.mean(ate_errors**2)))
    ate_mean = float(np.mean(ate_errors))
    ate_median = float(np.median(ate_errors))
    ate_std = float(np.std(ate_errors))
    ate_min = float(np.min(ate_errors))
    ate_max = float(np.max(ate_errors))

    rpe = _rpe_statistics(
        matched.ref_positions,
        matched.ref_orientations_wxyz,
        matched.ref_timestamps,
        matched_est_positions_aligned,
        matched_est_orientations_aligned_wxyz,
        matched.est_timestamps,
        config,
    )

    diffs = np.diff(eligible_positions, axis=0)
    dists = np.linalg.norm(diffs, axis=1)
    cum_dists_ok_deg = np.zeros(len(eligible_positions))
    cum_dists_ok_deg[1:] = np.cumsum(dists)
    cumulative_distance = float(cum_dists_ok_deg[-1]) if len(cum_dists_ok_deg) > 0 else 0.0
    cum_dists_matched = cum_dists_ok_deg[matched.matched_est_filt_idx]
    final_drift = float(ate_errors[-1]) if len(ate_errors) > 0 else 0.0

    ref_orientations_xyzw = matched.ref_orientations_wxyz[:, [1, 2, 3, 0]]
    heading_mean, heading_p95 = _heading_error_stats_deg(
        alignment.orientations_xyzw[matched.matched_est_orig_idx], ref_orientations_xyzw
    )

    return (
        MetricSummary(
            ate_rmse=ate_rmse,
            ate_mean=ate_mean,
            ate_median=ate_median,
            ate_std=ate_std,
            ate_min=ate_min,
            ate_max=ate_max,
            rpe_rmse=rpe["rmse"],
            rpe_mean=rpe["mean"],
            rpe_median=rpe["median"],
            rpe_std=rpe["std"],
            rpe_min=rpe["min"],
            rpe_max=rpe["max"],
            final_drift=final_drift,
            cumulative_distance=cumulative_distance,
            drift_percent=_drift_percent(final_drift, cumulative_distance),
            heading_error_mean_deg=heading_mean,
            heading_error_p95_deg=heading_p95,
            error_at_distance_m=_error_at_distance_markers(ate_errors, cum_dists_matched, config.distance_markers_m),
        ),
        ate_errors,
        cum_dists_matched,
    )


def _error_vs_time_rows(
    estimate: Trajectory,
    reference: Trajectory,
    matched: _MatchedTrajectoryData,
    alignment: _AlignmentData,
    health_labels: np.ndarray,
    ate_errors: np.ndarray,
) -> list[ErrorVsTimeRow]:
    rows = []
    orig_idx_to_matched_k = {orig_idx: k for k, orig_idx in enumerate(matched.matched_est_orig_idx)}
    for i, _timestamp in enumerate(estimate.timestamps):
        h_str = str(health_labels[i])
        ts = float(estimate.timestamps[i])
        est_xyz = alignment.positions[i].tolist()

        if i in orig_idx_to_matched_k:
            k = orig_idx_to_matched_k[i]
            ref_index = matched.matched_ref_idx[k]
            ref_xyz = reference.positions[ref_index].tolist()
            err_xyz = (alignment.positions[i] - reference.positions[ref_index]).tolist()
            err_mag = float(ate_errors[k])
            res_val = float(abs(ts - reference.timestamps[ref_index]))
        else:
            ref_xyz = None
            err_xyz = None
            err_mag = None
            res_val = None

        rows.append(
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
    return rows


def _error_vs_distance_rows(
    estimate: Trajectory,
    reference: Trajectory,
    matched: _MatchedTrajectoryData,
    health_labels: np.ndarray,
    ate_errors: np.ndarray,
    cum_dists_matched: np.ndarray,
    drift_bin_width_m: float,
) -> list[ErrorVsDistanceRow]:
    rows = []
    for k, orig_i in enumerate(matched.matched_est_orig_idx):
        dist = float(cum_dists_matched[k])
        err_mag = float(ate_errors[k])
        h_str = str(health_labels[orig_i])
        res_val = float(abs(estimate.timestamps[orig_i] - reference.timestamps[matched.matched_ref_idx[k]]))
        bin_start = float((dist // drift_bin_width_m) * drift_bin_width_m)
        bin_end = bin_start + drift_bin_width_m

        rows.append(
            ErrorVsDistanceRow(
                cumulative_distance=dist,
                error_magnitude=err_mag,
                health=h_str,
                association_residual=res_val,
                bin_start=bin_start,
                bin_end=bin_end,
            )
        )
    return rows


def _bin_error_summary(ate_errors: np.ndarray, in_bin: np.ndarray) -> tuple[int, float | None, float | None]:
    pose_count = int(np.sum(in_bin))
    if pose_count == 0:
        return pose_count, None, None
    bin_errors = ate_errors[in_bin]
    q75, q25 = np.percentile(bin_errors, [75, 25])
    return pose_count, float(np.median(bin_errors)), float(q75 - q25)


def _drift_bin_summaries(
    ate_errors: np.ndarray, cum_dists_matched: np.ndarray, drift_bin_width_m: float
) -> list[DriftBinSummary]:
    if len(cum_dists_matched) == 0:
        return []
    num_bins = max(int(np.ceil(cum_dists_matched[-1] / drift_bin_width_m)), 1)
    drift_bins = []
    for i in range(num_bins):
        b_start = float(i * drift_bin_width_m)
        b_end = b_start + drift_bin_width_m
        upper_mask = cum_dists_matched <= b_end if i == num_bins - 1 else cum_dists_matched < b_end
        in_bin = (cum_dists_matched >= b_start) & upper_mask
        pose_count, median_err, iqr_err = _bin_error_summary(ate_errors, in_bin)
        drift_bins.append(
            DriftBinSummary(
                bin_start=b_start,
                bin_end=b_end,
                median_error=median_err,
                iqr_error=iqr_err,
                pose_count=pose_count,
            )
        )
    return drift_bins


def _optional_sync_timestamp(value: Any) -> float | None:
    return float(value) if value is not None else None


def _evaluation_diagnostics(sync_diag: Any) -> EvaluationDiagnostics:
    return EvaluationDiagnostics(
        source_count=int(sync_diag.source_count),
        target_count=int(sync_diag.target_count),
        matched_count=int(sync_diag.matched_count),
        unmatched_source_count=int(sync_diag.unmatched_source_count),
        unmatched_target_count=int(sync_diag.unmatched_target_count),
        tolerance_sec=float(sync_diag.tolerance_sec),
        first_matched_timestamp=_optional_sync_timestamp(sync_diag.first_matched_timestamp),
        last_matched_timestamp=_optional_sync_timestamp(sync_diag.last_matched_timestamp),
        overlap_sufficiency=float(sync_diag.overlap_sufficiency),
    )


def _aligned_trajectories(
    estimate: Trajectory, reference: Trajectory, matched: _MatchedTrajectoryData, alignment: _AlignmentData
) -> tuple[Trajectory, Trajectory]:
    aligned_est_trajectory = Trajectory(
        timestamps=estimate.timestamps,
        method=estimate.method,
        positions=alignment.positions,
        orientations=alignment.orientations_xyzw,
        velocities=estimate.velocities,
        confidence=estimate.confidence,
        health=estimate.health,
        latency_ms=estimate.latency_ms,
    )

    matched_count = len(matched.matched_est_orig_idx)
    aligned_gt_trajectory = Trajectory(
        timestamps=matched.ref_timestamps,
        method="ground_truth",
        positions=matched.ref_positions,
        orientations=matched.ref_orientations_xyzw,
        velocities=reference.velocities[matched.matched_ref_idx] if reference.velocities is not None else None,
        confidence=reference.confidence[matched.matched_ref_idx] if reference.confidence is not None else None,
        health=np.array([PoseHealth.OK] * matched_count, dtype=object),
        latency_ms=reference.latency_ms[matched.matched_ref_idx] if reference.latency_ms is not None else None,
    )
    return aligned_est_trajectory, aligned_gt_trajectory


def evaluate_trajectory(estimate: Trajectory, reference: Trajectory, config: EvalConfig) -> EvaluationResult:
    """
    Evaluates an estimated trajectory against a ground-truth reference trajectory.
    """
    _validate_evaluation_trajectory("Estimate", estimate)
    _validate_evaluation_trajectory("Reference", reference)

    prepared = _prepare_evaluation(estimate)
    matched = _match_trajectories(estimate, reference, config, prepared.eligible_mask)
    alignment = _align_estimate(estimate, matched, config)
    metric_summary, ate_errors, cum_dists_matched = _metric_summary(
        matched,
        alignment,
        estimate.positions[prepared.eligible_mask],
        config,
    )
    error_vs_time = _error_vs_time_rows(
        estimate,
        reference,
        matched,
        alignment,
        prepared.health_labels,
        ate_errors,
    )
    error_vs_distance = _error_vs_distance_rows(
        estimate,
        reference,
        matched,
        prepared.health_labels,
        ate_errors,
        cum_dists_matched,
        config.drift_bin_width_m,
    )
    aligned_est_trajectory, aligned_gt_trajectory = _aligned_trajectories(estimate, reference, matched, alignment)

    return EvaluationResult(
        status="OK",
        error_message=None,
        config=config,
        diagnostics=_evaluation_diagnostics(matched.sync_diag),
        coverage=prepared.coverage,
        runtime=prepared.runtime,
        failures=prepared.failures,
        alignment=alignment.result,
        metrics=metric_summary,
        drift_bins=_drift_bin_summaries(ate_errors, cum_dists_matched, config.drift_bin_width_m),
        error_vs_time=error_vs_time,
        error_vs_distance=error_vs_distance,
        aligned_estimate=aligned_est_trajectory,
        aligned_ground_truth=aligned_gt_trajectory,
    )


def _json_number(val: float | np.floating | np.integer) -> float | int | None:
    if not np.isfinite(val):
        return None
    if isinstance(val, np.floating):
        return float(val)
    return int(val) if isinstance(val, np.integer) else val


def _json_dict(val: dict) -> dict:
    return {key: make_json_serializable(value) for key, value in val.items()}


def _json_list(val: list) -> list:
    return [make_json_serializable(value) for value in val]


def make_json_serializable(val: Any) -> Any:
    """Helper to convert objects/numpy types to standard JSON-compatible formats."""
    converters = (
        (dict, _json_dict),
        (list, _json_list),
        (np.ndarray, lambda array: make_json_serializable(array.tolist())),  # type: ignore[attr-defined]
        (Path, str),
    )
    for expected_type, converter in converters:
        if isinstance(val, expected_type):
            return converter(val)  # type: ignore[arg-type]
    if isinstance(val, (float, np.floating, np.integer)):
        return _json_number(val)
    if hasattr(val, "__dataclass_fields__"):
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
        writer.writerow(_error_vs_time_header())
        for row in result.error_vs_time:
            writer.writerow(_error_vs_time_csv_row(row))


def _error_vs_time_header() -> list[str]:
    return [
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


def _optional_xyz(values: list[float] | None) -> tuple[float | str, float | str, float | str]:
    if values and len(values) >= 3:
        return (values[0], values[1], values[2])
    return ("", "", "")


def _format_optional_float(value: float | None) -> str:
    return f"{value:.9f}" if value is not None else ""


def _format_csv_number(value: float | str) -> str:
    return f"{value:.9f}" if isinstance(value, float) else value


def _format_xyz(values: tuple[float | str, float | str, float | str]) -> list[str]:
    return [_format_csv_number(value) for value in values]


def _error_vs_time_csv_row(row: ErrorVsTimeRow) -> list[str]:
    gt_xyz = _optional_xyz(row.aligned_ground_truth_xyz)
    err_xyz = _optional_xyz(row.xyz_error)
    return [
        f"{row.timestamp:.9f}",
        f"{row.estimated_xyz[0]:.9f}",
        f"{row.estimated_xyz[1]:.9f}",
        f"{row.estimated_xyz[2]:.9f}",
        *_format_xyz(gt_xyz),
        *_format_xyz(err_xyz),
        _format_optional_float(row.error_magnitude),
        row.health,
        _format_optional_float(row.association_residual),
    ]


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
