"""Event+IMU odometry backend: IMU propagation corrected by event-frame shifts.

IMU integration is the backbone. Between consecutive fixed-time event frames a
phase-correlation shift is estimated (see :mod:`nav_benchmark.events.shift`),
the rotational flow predicted by the gyro is subtracted, and the residual
translational shift is converted to a world-frame displacement using the
propagated orientation, an assumed scene depth, and the camera focal length.
The difference between that event-derived displacement and the IMU displacement
is applied as a conservative, norm-bounded position correction.

Deliberate M002 simplifications (documented, revisable):
- The camera frame is assumed to coincide with the IMU/body frame (the MVSEC
  DAVIS IMU is mounted on the camera).
- Scene depth is a single configured constant, so absolute correction scale is
  approximate; the cue mainly bounds drift rather than tracking scale.
- The event cue corrects position only; orientation stays pure IMU.
"""

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial.transform import Rotation

from nav_benchmark.baselines.base import BaseOdometryBackend, EstimatorRunResult
from nav_benchmark.baselines.common import health_from_confidence, latency_per_sample_ms
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.datasets.mvsec import Calibration, MvsecSequence
from nav_benchmark.events.representations import ensure_event_frames
from nav_benchmark.events.shift import ShiftEstimate, estimate_frame_shift
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

_FALLBACK_FOCAL_LENGTH_PX = 200.0
_HEALTH_SEVERITY = {
    PoseHealth.OK.value: 0,
    PoseHealth.DEGRADED.value: 1,
    PoseHealth.LOST.value: 2,
    PoseHealth.INVALID.value: 3,
}


@dataclass
class EventImuConfig:
    """Configuration for the event-frame shift correction over IMU propagation.

    ``run_diagnostics`` is filled by the CLI runner after the backend executes
    so pair/coverage diagnostics land in ``run_manifest.json``.
    """

    imu_config: ImuOnlyConfig | None = None
    event_window_sec: float = 0.050
    focal_length_px: float | None = None
    assumed_scene_depth_m: float = 5.0
    gyro_compensation: bool = True
    correction_gain: float = 0.35
    max_correction_m_per_frame: float = 0.5
    min_shift_confidence: float = 0.10
    max_frame_gap_sec: float = 0.25
    base_imu_confidence: float = 0.35
    event_confidence_weight: float = 0.65
    ok_confidence_threshold: float = 0.55
    degraded_confidence_threshold: float = 0.15
    run_diagnostics: dict[str, float | int] | None = field(default=None, repr=False)


@dataclass
class _PairCue:
    """Per event-frame-pair outcome used for correction and health labeling."""

    t_start: float
    t_end: float
    confidence: float
    correction: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    applied: bool = False
    reason: str = "ok"


def _sequence_gravity(sequence: MvsecSequence) -> np.ndarray:
    if sequence.imu is not None and len(sequence.imu) > 0 and float(np.nanmedian(sequence.imu["az"])) < 0.0:
        return np.array([0.0, 0.0, -9.81], dtype=np.float64)
    return np.array([0.0, 0.0, 9.81], dtype=np.float64)


def _has_ground_truth(sequence: MvsecSequence) -> bool:
    return sequence.gt_poses is not None and len(sequence.gt_poses) > 0


def _initial_position_from_gt(gt) -> np.ndarray:
    return np.array([gt["x"][0], gt["y"][0], gt["z"][0]], dtype=np.float64)


def _initial_orientation_from_gt(gt) -> np.ndarray:
    return np.array([gt["qx"][0], gt["qy"][0], gt["qz"][0], gt["qw"][0]], dtype=np.float64)


def _initial_velocity_from_gt(gt) -> np.ndarray | None:
    if len(gt) < 2:
        return None
    dt = float(gt["t"][1] - gt["t"][0])
    if dt <= 0.0:
        return None
    return (_initial_position_from_gt(gt[1:]) - _initial_position_from_gt(gt)) / dt


def _default_imu_config_from_sequence(sequence: MvsecSequence) -> ImuOnlyConfig:
    cfg = ImuOnlyConfig()
    cfg.gravity = _sequence_gravity(sequence)
    if not _has_ground_truth(sequence):
        return cfg

    gt = sequence.gt_poses
    cfg.initial_position = _initial_position_from_gt(gt)
    cfg.initial_orientation = _initial_orientation_from_gt(gt)
    initial_velocity = _initial_velocity_from_gt(gt)
    if initial_velocity is not None:
        cfg.initial_velocity = initial_velocity
    return cfg


def _event_imu_config(config: EventImuConfig | None) -> EventImuConfig:
    return config if config is not None else EventImuConfig()


def _imu_config_for_event_run(config: EventImuConfig, sequence: MvsecSequence) -> ImuOnlyConfig:
    return config.imu_config if config.imu_config is not None else _default_imu_config_from_sequence(sequence)


def _focal_from_calibration(sequence: MvsecSequence) -> float | None:
    intrinsics = sequence.calibration.data.get("K")
    if intrinsics is None:
        return None
    matrix = np.asarray(intrinsics, dtype=np.float64).reshape(-1)
    if matrix.size >= 1 and np.isfinite(matrix[0]) and matrix[0] > 0.0:
        return float(matrix[0])
    return None


def _resolve_focal_length_px(sequence: MvsecSequence, config: EventImuConfig) -> float:
    if config.focal_length_px is not None:
        return float(config.focal_length_px)
    calibrated = _focal_from_calibration(sequence)
    if calibrated is not None:
        return calibrated
    return _FALLBACK_FOCAL_LENGTH_PX


def _require_event_frames(sequence: MvsecSequence, config: EventImuConfig) -> tuple[np.ndarray, np.ndarray]:
    if sequence.event_frames is None:
        ensure_event_frames(sequence, window_sec=config.event_window_sec)
    frames = sequence.event_frames
    timestamps = sequence.event_frame_timestamps
    if frames is None or timestamps is None or len(timestamps) == 0:
        raise ValueError(
            "event_imu requires event frames: the sequence has no event_frames stream "
            "and no raw events to build them from"
        )
    return frames, np.asarray(timestamps, dtype=np.float64)


def _interp_positions(imu_t: np.ndarray, positions: np.ndarray, at_t: float) -> np.ndarray:
    return np.array([np.interp(at_t, imu_t, positions[:, axis]) for axis in range(3)], dtype=np.float64)


def _mean_angular_velocity(imu: np.ndarray, t_start: float, t_end: float) -> np.ndarray:
    t = np.asarray(imu["t"], dtype=np.float64)
    mask = (t >= t_start) & (t <= t_end)
    if not np.any(mask):
        nearest = int(np.argmin(np.abs(t - 0.5 * (t_start + t_end))))
        mask = np.zeros(len(t), dtype=bool)
        mask[nearest] = True
    return np.array(
        [float(np.mean(imu["gx"][mask])), float(np.mean(imu["gy"][mask])), float(np.mean(imu["gz"][mask]))],
        dtype=np.float64,
    )


def _rotational_flow_px(omega_cam: np.ndarray, focal_px: float, dt: float) -> np.ndarray:
    # Small-angle rotational optical flow at the image center for a pinhole
    # camera with x right, y down, z forward: (u_dot, v_dot) = f * (-w_y, w_x).
    return focal_px * dt * np.array([-omega_cam[1], omega_cam[0]], dtype=np.float64)


def _camera_velocity_from_shift(shift_px: np.ndarray, focal_px: float, depth_m: float, dt: float) -> np.ndarray:
    # Translational flow at the image center: (u_dot, v_dot) = -f/Z * (tx, ty).
    velocity_xy = -shift_px / dt * depth_m / focal_px
    return np.array([velocity_xy[0], velocity_xy[1], 0.0], dtype=np.float64)


def _orientation_at(imu_t: np.ndarray, orientations: np.ndarray, at_t: float) -> Rotation:
    index = int(np.argmin(np.abs(imu_t - at_t)))
    return Rotation.from_quat(orientations[index])


def _bounded_correction(innovation: np.ndarray, confidence: float, config: EventImuConfig) -> np.ndarray:
    correction = config.correction_gain * confidence * innovation
    norm = float(np.linalg.norm(correction))
    if norm > config.max_correction_m_per_frame:
        correction = correction * (config.max_correction_m_per_frame / norm)
    return correction



def _extrinsics_rotation_from_calibration(calibration: Calibration) -> tuple[Rotation | None, str | None]:
    if not calibration.imu_cam_transform_available or "T_imu_cam" not in calibration.data:
        return None, None

    T = calibration.data["T_imu_cam"]
    try:
        T = np.asarray(T, dtype=np.float64).reshape(4, 4)
    except Exception:
        return None, "malformed_shape"

    R = T[:3, :3]
    if not np.all(np.isfinite(R)):
        return None, "non_finite_elements"

    det = np.linalg.det(R)
    if abs(det - 1.0) >= 1e-4:
        return None, "degenerate_determinant"

    # T_imu_cam transforms FROM imu TO camera.
    # We want to transform event displacements in camera frame TO body frame.
    # Therefore, we want the inverse of this rotation.
    return Rotation.from_matrix(R).inv(), None


def _event_world_displacement(
    estimate: ShiftEstimate,
    t_start: float,
    t_end: float,
    imu: np.ndarray,
    imu_trajectory: Trajectory,
    focal_px: float,
    config: EventImuConfig,
    cam_to_body: Rotation | None = None,
) -> np.ndarray:
    dt = t_end - t_start
    shift = estimate.shift_px
    if config.gyro_compensation:
        omega = _mean_angular_velocity(imu, t_start, t_end)
        shift = shift - _rotational_flow_px(omega, focal_px, dt)

    velocity_cam = _camera_velocity_from_shift(shift, focal_px, config.assumed_scene_depth_m, dt)
    velocity_body = cam_to_body.apply(velocity_cam) if cam_to_body is not None else velocity_cam

    rotation_world_body = _orientation_at(
        imu_trajectory.timestamps, imu_trajectory.orientations, 0.5 * (t_start + t_end)
    )
    return rotation_world_body.apply(velocity_body) * dt


def _imu_displacement(imu_trajectory: Trajectory, t_start: float, t_end: float) -> np.ndarray:
    imu_t = np.asarray(imu_trajectory.timestamps, dtype=np.float64)
    return _interp_positions(imu_t, imu_trajectory.positions, t_end) - _interp_positions(
        imu_t, imu_trajectory.positions, t_start
    )


def _unusable_cue(cue: _PairCue, estimate: ShiftEstimate) -> _PairCue:
    cue.confidence = 0.0
    cue.reason = estimate.reason if not estimate.valid else "non_positive_dt"
    return cue


def _pair_cue(
    estimate: ShiftEstimate,
    t_start: float,
    t_end: float,
    imu: np.ndarray,
    imu_trajectory: Trajectory,
    focal_px: float,
    config: EventImuConfig,
    cam_to_body: Rotation | None = None,
) -> _PairCue:
    cue = _PairCue(t_start=t_start, t_end=t_end, confidence=estimate.confidence, reason=estimate.reason)
    if not estimate.valid or t_end - t_start <= 0.0:
        return _unusable_cue(cue, estimate)
    if estimate.confidence < config.min_shift_confidence:
        cue.reason = "low_confidence"
        return cue

    displacement_event = _event_world_displacement(estimate, t_start, t_end, imu, imu_trajectory, focal_px, config, cam_to_body)
    innovation = displacement_event - _imu_displacement(imu_trajectory, t_start, t_end)
    if not np.all(np.isfinite(innovation)):
        cue.confidence = 0.0
        cue.reason = "non_finite_innovation"
        return cue

    cue.correction = _bounded_correction(innovation, estimate.confidence, config)
    cue.applied = True
    return cue


def _accumulated_offsets(imu_t: np.ndarray, cues: list[_PairCue]) -> np.ndarray:
    offsets = np.zeros((len(imu_t), 3), dtype=np.float64)
    for cue in cues:
        if not cue.applied:
            continue
        after = imu_t > cue.t_end
        offsets[after] += cue.correction
        inside = (imu_t > cue.t_start) & (imu_t <= cue.t_end)
        if np.any(inside):
            fraction = (imu_t[inside] - cue.t_start) / (cue.t_end - cue.t_start)
            offsets[inside] += fraction[:, np.newaxis] * cue.correction
    return offsets


def _sampled_event_confidence(imu_t: np.ndarray, cues: list[_PairCue]) -> tuple[np.ndarray, np.ndarray]:
    """Per-IMU-sample event-cue confidence and whether a correction covers the sample."""
    confidence = np.zeros(len(imu_t), dtype=np.float64)
    corrected = np.zeros(len(imu_t), dtype=bool)
    for cue in cues:
        inside = (imu_t > cue.t_start) & (imu_t <= cue.t_end)
        confidence[inside] = cue.confidence
        if cue.applied:
            corrected[inside] = True
    return confidence, corrected


def _coverage_mask(imu_t: np.ndarray, frame_t: np.ndarray, max_gap_sec: float) -> np.ndarray:
    if len(frame_t) == 0:
        return np.zeros(len(imu_t), dtype=bool)
    return (imu_t >= frame_t[0] - max_gap_sec) & (imu_t <= frame_t[-1] + max_gap_sec)


def _worse_health(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    result = a.copy()
    for i in range(len(a)):
        if _HEALTH_SEVERITY.get(str(b[i]), 0) > _HEALTH_SEVERITY.get(str(a[i]), 0):
            result[i] = b[i]
    return result


def _velocities_with_offsets(imu_trajectory: Trajectory, imu_t: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    velocities = (
        imu_trajectory.velocities.copy()
        if imu_trajectory.velocities is not None
        else np.zeros_like(imu_trajectory.positions)
    )
    if len(imu_t) >= 2:
        dt = np.diff(imu_t)
        dt[dt <= 0.0] = 1e-9
        velocities[:-1] += np.diff(offsets, axis=0) / dt[:, np.newaxis]
    return velocities


def _build_cues(
    frames: np.ndarray,
    frame_t: np.ndarray,
    imu: np.ndarray,
    imu_trajectory: Trajectory,
    focal_px: float,
    config: EventImuConfig,
    cam_to_body: Rotation | None = None,
) -> list[_PairCue]:
    return [
        _pair_cue(
            estimate_frame_shift(frames[i - 1], frames[i]),
            float(frame_t[i - 1]),
            float(frame_t[i]),
            imu,
            imu_trajectory,
            focal_px,
            config,
            cam_to_body,
        )
        for i in range(1, len(frame_t))
    ]


def _merged_health(
    confidence: np.ndarray,
    imu_trajectory: Trajectory,
    corrected: np.ndarray,
    imu_t: np.ndarray,
    config: EventImuConfig,
) -> np.ndarray:
    health = health_from_confidence(
        confidence,
        ok_threshold=config.ok_confidence_threshold,
        degraded_threshold=config.degraded_confidence_threshold,
    )
    # Where no event correction bounds the drift, IMU propagation health
    # (time/drift escalation) must not be masked by the base confidence.
    imu_health_labels = (
        [str(value) for value in imu_trajectory.health]
        if imu_trajectory.health is not None
        else [PoseHealth.OK.value] * len(imu_t)
    )
    imu_health = np.array(imu_health_labels, dtype=object)
    uncorrected = ~corrected
    health[uncorrected] = _worse_health(health[uncorrected], imu_health[uncorrected])
    health[0] = imu_health[0]
    return health


def _cue_counts(cues: list[_PairCue]) -> tuple[int, int]:
    applied = 0
    invalid = 0
    for cue in cues:
        if cue.applied:
            applied += 1
        elif cue.confidence == 0.0:
            invalid += 1
    return applied, invalid


def _diagnostics_summary(
    cues: list[_PairCue],
    frame_t: np.ndarray,
    covered: np.ndarray,
    imu_t: np.ndarray,
    focal_px: float,
) -> dict[str, float | int | str | bool]:
    applied_count, invalid_count = _cue_counts(cues)
    mean_confidence = float(np.mean([cue.confidence for cue in cues])) if cues else 0.0
    return {
        "event_frame_count": len(frame_t),
        "event_pair_count": len(cues),
        "corrected_pair_count": applied_count,
        "skipped_pair_count": len(cues) - applied_count,
        "invalid_pair_count": invalid_count,
        "mean_pair_confidence": mean_confidence,
        "imu_samples_covered_fraction": float(np.count_nonzero(covered) / max(len(imu_t), 1)),
        "focal_length_px": focal_px,
    }


def _combined_latency(start_time: float, imu_trajectory: Trajectory, count: int) -> np.ndarray:
    latency_ms = latency_per_sample_ms(start_time, count)
    if imu_trajectory.latency_ms is not None:
        latency_ms = latency_ms + imu_trajectory.latency_ms
    return latency_ms


class EventImuBackend(BaseOdometryBackend):
    """Deterministic event-frame shift correction over IMU propagation."""

    method = "event_imu"
    required_streams = ("imu", "event_frames")

    def __init__(self) -> None:
        self.diagnostics: dict[str, float | int | str | bool] = {}

    def run(self, sequence: MvsecSequence, *, config: EventImuConfig | None = None) -> Trajectory:
        cfg = _event_imu_config(config)
        start_time = time.perf_counter()

        imu_config = _imu_config_for_event_run(cfg, sequence)
        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        imu = sequence.imu
        if imu is None:
            raise ValueError("event_imu requires IMU data in the sequence")
        frames, frame_t = _require_event_frames(sequence, cfg)
        focal_px = _resolve_focal_length_px(sequence, cfg)

        cam_to_body, rejected_reason = _extrinsics_rotation_from_calibration(sequence.calibration)
        if cam_to_body is not None:
            self.diagnostics["extrinsics_applied"] = True
            self.diagnostics["extrinsics_source"] = "calibration"
        else:
            self.diagnostics["extrinsics_applied"] = False
            self.diagnostics["extrinsics_source"] = "identity_fallback"
            if rejected_reason:
                self.diagnostics["extrinsics_rejected_reason"] = rejected_reason

        cues = _build_cues(frames, frame_t, imu, imu_trajectory, focal_px, cfg, cam_to_body)

        imu_t = np.asarray(imu_trajectory.timestamps, dtype=np.float64)
        offsets = _accumulated_offsets(imu_t, cues)
        positions = imu_trajectory.positions + offsets
        velocities = _velocities_with_offsets(imu_trajectory, imu_t, offsets)

        event_confidence, corrected = _sampled_event_confidence(imu_t, cues)
        covered = _coverage_mask(imu_t, frame_t, cfg.max_frame_gap_sec)
        event_confidence = np.where(covered, event_confidence, 0.0)

        confidence = np.clip(cfg.base_imu_confidence + cfg.event_confidence_weight * event_confidence, 0.0, 1.0)
        health = _merged_health(confidence, imu_trajectory, corrected, imu_t, cfg)
        self.diagnostics.update(_diagnostics_summary(cues, frame_t, covered, imu_t, focal_px))

        return Trajectory(
            timestamps=imu_trajectory.timestamps,
            method=self.method,
            positions=positions,
            orientations=imu_trajectory.orientations,
            velocities=velocities,
            confidence=confidence,
            health=health,
            latency_ms=_combined_latency(start_time, imu_trajectory, len(imu_t)),
        )

    def run_result(self, sequence: MvsecSequence, *, config: EventImuConfig | None = None) -> EstimatorRunResult:
        result = super().run_result(sequence, config=config)
        result.diagnostics.update(self.diagnostics)
        return result
