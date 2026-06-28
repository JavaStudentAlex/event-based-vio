import time
from dataclasses import dataclass, field

import numpy as np

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.baselines.common import (
    health_from_confidence,
    interpolate_trajectory,
    latency_per_sample_ms,
)
from nav_benchmark.baselines.event_imu import _default_imu_config_from_sequence, _weighted_quaternion_blend
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.baselines.visual import FeatureVoConfig, RgbVoBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass
class ImageImuConfig:
    """Configuration for the RGB-frame plus IMU complementary fusion baseline."""

    imu_config: ImuOnlyConfig | None = None
    rgb_vo_config: FeatureVoConfig = field(default_factory=lambda: FeatureVoConfig(scale_bias=1.01))
    image_correction_gain: float = 0.70
    min_image_confidence_for_correction: float = 0.15
    ok_confidence_threshold: float = 0.60
    degraded_confidence_threshold: float = 0.20


class ImageImuBackend(BaseOdometryBackend):
    """Simple deterministic RGB VO correction over IMU prediction."""

    method = "image_imu"
    required_streams = ("imu", "images")

    def run(self, sequence: MvsecSequence, *, config: ImageImuConfig | None = None) -> Trajectory:
        cfg = config if config is not None else ImageImuConfig()
        start_time = time.perf_counter()

        imu_config = cfg.imu_config if cfg.imu_config is not None else _default_imu_config_from_sequence(sequence)
        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        rgb_trajectory = RgbVoBackend().run(sequence, config=cfg.rgb_vo_config)

        rgb_on_imu = interpolate_trajectory(rgb_trajectory, imu_trajectory.timestamps)
        rgb_confidence = np.where(
            rgb_on_imu.confidence >= cfg.min_image_confidence_for_correction,
            rgb_on_imu.confidence,
            0.0,
        )
        correction_weight = np.clip(cfg.image_correction_gain * rgb_confidence, 0.0, cfg.image_correction_gain)

        positions = (1.0 - correction_weight[:, np.newaxis]) * imu_trajectory.positions
        positions += correction_weight[:, np.newaxis] * rgb_on_imu.positions

        imu_velocity = imu_trajectory.velocities if imu_trajectory.velocities is not None else np.zeros_like(positions)
        velocities = (1.0 - correction_weight[:, np.newaxis]) * imu_velocity
        velocities += correction_weight[:, np.newaxis] * rgb_on_imu.velocities

        orientations = _weighted_quaternion_blend(
            imu_trajectory.orientations, rgb_on_imu.orientations, correction_weight
        )

        imu_confidence = (
            imu_trajectory.confidence
            if imu_trajectory.confidence is not None
            else np.ones(len(imu_trajectory.timestamps))
        )
        confidence = np.clip(0.40 * imu_confidence + 0.60 * rgb_on_imu.confidence, 0.0, 1.0)
        confidence = np.where(rgb_on_imu.in_range, confidence, np.minimum(confidence, 0.40))

        health = health_from_confidence(
            confidence,
            ok_threshold=cfg.ok_confidence_threshold,
            degraded_threshold=cfg.degraded_confidence_threshold,
        )
        health[confidence <= 0.0] = PoseHealth.INVALID.value

        latency_ms = latency_per_sample_ms(start_time, len(imu_trajectory.timestamps))
        if imu_trajectory.latency_ms is not None:
            latency_ms += imu_trajectory.latency_ms
        if rgb_trajectory.latency_ms is not None and len(rgb_trajectory.latency_ms) > 0:
            latency_ms += float(np.nanmean(rgb_trajectory.latency_ms))

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
