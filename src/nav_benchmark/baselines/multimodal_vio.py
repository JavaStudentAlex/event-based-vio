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
from nav_benchmark.baselines.visual import EventVoBackend, FeatureVoConfig, RgbVoBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


@dataclass
class MultimodalVioConfig:
    """Configuration for the tri-modal (RGB + Event + IMU) complementary fusion baseline."""

    imu_config: ImuOnlyConfig | None = None
    rgb_vo_config: FeatureVoConfig = field(default_factory=lambda: FeatureVoConfig(scale_bias=1.01))
    event_vo_config: FeatureVoConfig = field(default_factory=lambda: FeatureVoConfig(scale_bias=0.98))
    image_correction_gain: float = 0.50
    event_correction_gain: float = 0.50
    min_confidence_for_correction: float = 0.10
    ok_confidence_threshold: float = 0.55
    degraded_confidence_threshold: float = 0.15


class MultimodalVioBackend(BaseOdometryBackend):
    """Simple deterministic RGB and Event VO correction over IMU prediction."""

    method = "multimodal_vio"
    required_streams = ("imu", "images", "event_frames")

    def run(self, sequence: MvsecSequence, *, config: MultimodalVioConfig | None = None) -> Trajectory:
        cfg = config if config is not None else MultimodalVioConfig()
        start_time = time.perf_counter()

        imu_config = cfg.imu_config if cfg.imu_config is not None else _default_imu_config_from_sequence(sequence)
        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        rgb_trajectory = RgbVoBackend().run(sequence, config=cfg.rgb_vo_config)
        event_trajectory = EventVoBackend().run(sequence, config=cfg.event_vo_config)

        rgb_on_imu = interpolate_trajectory(rgb_trajectory, imu_trajectory.timestamps)
        event_on_imu = interpolate_trajectory(event_trajectory, imu_trajectory.timestamps)

        rgb_confidence = np.where(
            rgb_on_imu.confidence >= cfg.min_confidence_for_correction,
            rgb_on_imu.confidence,
            0.0,
        )
        event_confidence = np.where(
            event_on_imu.confidence >= cfg.min_confidence_for_correction,
            event_on_imu.confidence,
            0.0,
        )

        w_rgb = np.clip(cfg.image_correction_gain * rgb_confidence, 0.0, cfg.image_correction_gain)
        w_evt = np.clip(cfg.event_correction_gain * event_confidence, 0.0, cfg.event_correction_gain)

        w_sum = w_rgb + w_evt
        w_imu = np.maximum(0.0, 1.0 - w_sum)

        scale = np.where(w_sum > 1.0, 1.0 / w_sum, 1.0)
        w_rgb = w_rgb * scale
        w_evt = w_evt * scale

        positions = w_imu[:, np.newaxis] * imu_trajectory.positions
        positions += w_rgb[:, np.newaxis] * rgb_on_imu.positions
        positions += w_evt[:, np.newaxis] * event_on_imu.positions

        imu_velocity = imu_trajectory.velocities if imu_trajectory.velocities is not None else np.zeros_like(positions)
        velocities = w_imu[:, np.newaxis] * imu_velocity
        velocities += w_rgb[:, np.newaxis] * rgb_on_imu.velocities
        velocities += w_evt[:, np.newaxis] * event_on_imu.velocities

        orientations = _weighted_quaternion_blend(
            imu_trajectory.orientations, rgb_on_imu.orientations, w_rgb / np.maximum(w_imu + w_rgb, 1e-9)
        )
        orientations = _weighted_quaternion_blend(
            orientations, event_on_imu.orientations, w_evt / np.maximum(1.0, 1e-9)
        )

        imu_confidence = (
            imu_trajectory.confidence
            if imu_trajectory.confidence is not None
            else np.ones(len(imu_trajectory.timestamps))
        )

        confidence = np.clip(
            0.30 * imu_confidence + 0.35 * rgb_on_imu.confidence + 0.35 * event_on_imu.confidence, 0.0, 1.0
        )

        in_range = rgb_on_imu.in_range | event_on_imu.in_range
        confidence = np.where(in_range, confidence, np.minimum(confidence, 0.30))

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
