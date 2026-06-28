import time
from dataclasses import dataclass, field

import numpy as np

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.baselines.common import (
    health_from_confidence,
    interpolate_trajectory,
    latency_per_sample_ms,
    normalize_quaternions,
)
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.baselines.visual import EventVoBackend, FeatureVoConfig
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass
class EventImuConfig:
    """Configuration for the event-frame plus IMU complementary fusion baseline."""

    imu_config: ImuOnlyConfig | None = None
    event_vo_config: FeatureVoConfig = field(default_factory=lambda: FeatureVoConfig(scale_bias=0.98))
    event_correction_gain: float = 0.65
    min_event_confidence_for_correction: float = 0.10
    ok_confidence_threshold: float = 0.55
    degraded_confidence_threshold: float = 0.15


def _default_imu_config_from_sequence(sequence: MvsecSequence) -> ImuOnlyConfig:
    cfg = ImuOnlyConfig()
    if sequence.imu is not None and len(sequence.imu) > 0 and float(np.nanmedian(sequence.imu["az"])) < 0.0:
        cfg.gravity = np.array([0.0, 0.0, -9.81], dtype=np.float64)
    if sequence.gt_poses is None or len(sequence.gt_poses) == 0:
        return cfg

    gt = sequence.gt_poses
    cfg.initial_position = np.array([gt["x"][0], gt["y"][0], gt["z"][0]], dtype=np.float64)
    cfg.initial_orientation = np.array([gt["qx"][0], gt["qy"][0], gt["qz"][0], gt["qw"][0]], dtype=np.float64)
    if len(gt) >= 2:
        dt = float(gt["t"][1] - gt["t"][0])
        if dt > 0.0:
            p0 = np.array([gt["x"][0], gt["y"][0], gt["z"][0]], dtype=np.float64)
            p1 = np.array([gt["x"][1], gt["y"][1], gt["z"][1]], dtype=np.float64)
            cfg.initial_velocity = (p1 - p0) / dt
    return cfg


def _weighted_quaternion_blend(a: np.ndarray, b: np.ndarray, weight_b: np.ndarray) -> np.ndarray:
    out = np.zeros_like(a)
    for i in range(len(a)):
        qa = a[i]
        qb = b[i]
        if float(np.dot(qa, qb)) < 0.0:
            qb = -qb
        w = float(np.clip(weight_b[i], 0.0, 1.0))
        out[i] = (1.0 - w) * qa + w * qb
    return normalize_quaternions(out)


class EventImuBackend(BaseOdometryBackend):
    """Simple deterministic event-frame VO correction over IMU prediction."""

    method = "event_imu"
    required_streams = ("imu", "event_frames")

    def run(self, sequence: MvsecSequence, *, config: EventImuConfig | None = None) -> Trajectory:
        cfg = config if config is not None else EventImuConfig()
        start_time = time.perf_counter()

        imu_config = cfg.imu_config if cfg.imu_config is not None else _default_imu_config_from_sequence(sequence)
        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        event_trajectory = EventVoBackend().run(sequence, config=cfg.event_vo_config)

        event_on_imu = interpolate_trajectory(event_trajectory, imu_trajectory.timestamps)
        event_confidence = np.where(
            event_on_imu.confidence >= cfg.min_event_confidence_for_correction,
            event_on_imu.confidence,
            0.0,
        )
        correction_weight = np.clip(cfg.event_correction_gain * event_confidence, 0.0, cfg.event_correction_gain)

        positions = (1.0 - correction_weight[:, np.newaxis]) * imu_trajectory.positions
        positions += correction_weight[:, np.newaxis] * event_on_imu.positions

        imu_velocity = imu_trajectory.velocities if imu_trajectory.velocities is not None else np.zeros_like(positions)
        velocities = (1.0 - correction_weight[:, np.newaxis]) * imu_velocity
        velocities += correction_weight[:, np.newaxis] * event_on_imu.velocities

        orientations = _weighted_quaternion_blend(
            imu_trajectory.orientations, event_on_imu.orientations, correction_weight
        )

        imu_confidence = (
            imu_trajectory.confidence
            if imu_trajectory.confidence is not None
            else np.ones(len(imu_trajectory.timestamps))
        )
        confidence = np.clip(0.35 * imu_confidence + 0.65 * event_on_imu.confidence, 0.0, 1.0)
        confidence = np.where(event_on_imu.in_range, confidence, np.minimum(confidence, 0.35))

        health = health_from_confidence(
            confidence,
            ok_threshold=cfg.ok_confidence_threshold,
            degraded_threshold=cfg.degraded_confidence_threshold,
        )
        health[confidence <= 0.0] = PoseHealth.INVALID.value

        latency_ms = latency_per_sample_ms(start_time, len(imu_trajectory.timestamps))
        if imu_trajectory.latency_ms is not None:
            latency_ms += imu_trajectory.latency_ms
        if event_trajectory.latency_ms is not None and len(event_trajectory.latency_ms) > 0:
            latency_ms += float(np.nanmean(event_trajectory.latency_ms))

        return Trajectory(
            timestamps=imu_trajectory.timestamps,
            method=self.method,
            positions=positions,
            orientations=orientations,
            velocities=velocities,
            confidence=confidence,
            health=health,
            latency_ms=latency_ms,
        )
