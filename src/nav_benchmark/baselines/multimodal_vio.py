import time
from dataclasses import dataclass, field

import numpy as np

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.baselines.common import (
    health_from_confidence,
    interpolate_trajectory,
    latency_per_sample_ms,
    weighted_quaternion_blend,
)
from nav_benchmark.baselines.event_imu import _default_imu_config_from_sequence
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


def _multimodal_config(config: MultimodalVioConfig | None) -> MultimodalVioConfig:
    return config if config is not None else MultimodalVioConfig()


def _multimodal_imu_config(config: MultimodalVioConfig, sequence: MvsecSequence) -> ImuOnlyConfig:
    return config.imu_config if config.imu_config is not None else _default_imu_config_from_sequence(sequence)


def _confidence_for_correction(confidence: np.ndarray, threshold: float) -> np.ndarray:
    return np.where(confidence >= threshold, confidence, 0.0)


def _correction_weights(
    rgb_on_imu,
    event_on_imu,
    config: MultimodalVioConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb_confidence = _confidence_for_correction(rgb_on_imu.confidence, config.min_confidence_for_correction)
    event_confidence = _confidence_for_correction(event_on_imu.confidence, config.min_confidence_for_correction)
    w_rgb = np.clip(config.image_correction_gain * rgb_confidence, 0.0, config.image_correction_gain)
    w_evt = np.clip(config.event_correction_gain * event_confidence, 0.0, config.event_correction_gain)
    w_sum = w_rgb + w_evt
    scale = np.where(w_sum > 1.0, 1.0 / w_sum, 1.0)
    return np.maximum(0.0, 1.0 - w_sum), w_rgb * scale, w_evt * scale


def _fused_positions(imu_trajectory: Trajectory, rgb_on_imu, event_on_imu, w_imu, w_rgb, w_evt) -> np.ndarray:
    positions = w_imu[:, np.newaxis] * imu_trajectory.positions
    positions += w_rgb[:, np.newaxis] * rgb_on_imu.positions
    positions += w_evt[:, np.newaxis] * event_on_imu.positions
    return positions


def _fused_velocities(
    imu_trajectory: Trajectory, rgb_on_imu, event_on_imu, weights, positions: np.ndarray
) -> np.ndarray:
    w_imu, w_rgb, w_evt = weights
    imu_velocity = imu_trajectory.velocities if imu_trajectory.velocities is not None else np.zeros_like(positions)
    velocities = w_imu[:, np.newaxis] * imu_velocity
    velocities += w_rgb[:, np.newaxis] * rgb_on_imu.velocities
    velocities += w_evt[:, np.newaxis] * event_on_imu.velocities
    return velocities


def _fused_orientations(imu_trajectory: Trajectory, rgb_on_imu, event_on_imu, w_imu, w_rgb, w_evt) -> np.ndarray:
    orientations = weighted_quaternion_blend(
        imu_trajectory.orientations,
        rgb_on_imu.orientations,
        w_rgb / np.maximum(w_imu + w_rgb, 1e-9),
    )
    return weighted_quaternion_blend(orientations, event_on_imu.orientations, w_evt / np.maximum(1.0, 1e-9))


def _imu_confidence(imu_trajectory: Trajectory) -> np.ndarray:
    if imu_trajectory.confidence is None:
        return np.ones(len(imu_trajectory.timestamps))
    return imu_trajectory.confidence


def _multimodal_confidence(imu_trajectory: Trajectory, rgb_on_imu, event_on_imu) -> np.ndarray:
    confidence = np.clip(
        0.30 * _imu_confidence(imu_trajectory) + 0.35 * rgb_on_imu.confidence + 0.35 * event_on_imu.confidence,
        0.0,
        1.0,
    )
    in_range = rgb_on_imu.in_range | event_on_imu.in_range
    return np.where(in_range, confidence, np.minimum(confidence, 0.30))


def _multimodal_latency(
    start_time: float, imu_trajectory: Trajectory, rgb_trajectory: Trajectory, event_trajectory: Trajectory
):
    latency_ms = latency_per_sample_ms(start_time, len(imu_trajectory.timestamps))
    if imu_trajectory.latency_ms is not None:
        latency_ms += imu_trajectory.latency_ms
    if rgb_trajectory.latency_ms is not None and len(rgb_trajectory.latency_ms) > 0:
        latency_ms += float(np.nanmean(rgb_trajectory.latency_ms))
    if event_trajectory.latency_ms is not None and len(event_trajectory.latency_ms) > 0:
        latency_ms += float(np.nanmean(event_trajectory.latency_ms))
    return latency_ms


class MultimodalVioBackend(BaseOdometryBackend):
    """Simple deterministic RGB and Event VO correction over IMU prediction."""

    method = "multimodal_vio"
    required_streams = ("imu", "images", "event_frames")

    def run(self, sequence: MvsecSequence, *, config: MultimodalVioConfig | None = None) -> Trajectory:
        cfg = _multimodal_config(config)
        start_time = time.perf_counter()

        imu_config = _multimodal_imu_config(cfg, sequence)
        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        rgb_trajectory = RgbVoBackend().run(sequence, config=cfg.rgb_vo_config)
        event_trajectory = EventVoBackend().run(sequence, config=cfg.event_vo_config)

        rgb_on_imu = interpolate_trajectory(rgb_trajectory, imu_trajectory.timestamps)
        event_on_imu = interpolate_trajectory(event_trajectory, imu_trajectory.timestamps)
        w_imu, w_rgb, w_evt = _correction_weights(rgb_on_imu, event_on_imu, cfg)

        positions = _fused_positions(imu_trajectory, rgb_on_imu, event_on_imu, w_imu, w_rgb, w_evt)
        velocities = _fused_velocities(imu_trajectory, rgb_on_imu, event_on_imu, (w_imu, w_rgb, w_evt), positions)
        orientations = _fused_orientations(imu_trajectory, rgb_on_imu, event_on_imu, w_imu, w_rgb, w_evt)
        confidence = _multimodal_confidence(imu_trajectory, rgb_on_imu, event_on_imu)
        health = health_from_confidence(
            confidence,
            ok_threshold=cfg.ok_confidence_threshold,
            degraded_threshold=cfg.degraded_confidence_threshold,
        )
        health[confidence <= 0.0] = PoseHealth.INVALID.value

        return Trajectory(
            timestamps=imu_trajectory.timestamps,
            method=self.method,
            positions=positions,
            orientations=orientations,
            velocities=velocities,
            confidence=confidence,
            health=health,
            latency_ms=_multimodal_latency(start_time, imu_trajectory, rgb_trajectory, event_trajectory),
        )
