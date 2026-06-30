import time
from dataclasses import dataclass, field

import numpy as np

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.baselines.common import (
    fuse_imu_and_visual,
)
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.baselines.visual import EventVoBackend, FeatureVoConfig
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import Trajectory


@dataclass
class EventImuConfig:
    """Configuration for the event-frame plus IMU complementary fusion baseline."""

    imu_config: ImuOnlyConfig | None = None
    event_vo_config: FeatureVoConfig = field(default_factory=lambda: FeatureVoConfig(scale_bias=0.98))
    event_correction_gain: float = 0.65
    min_event_confidence_for_correction: float = 0.10
    ok_confidence_threshold: float = 0.55
    degraded_confidence_threshold: float = 0.15


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


class EventImuBackend(BaseOdometryBackend):
    """Simple deterministic event-frame VO correction over IMU prediction."""

    method = "event_imu"
    required_streams = ("imu", "event_frames")

    def run(self, sequence: MvsecSequence, *, config: EventImuConfig | None = None) -> Trajectory:
        cfg = _event_imu_config(config)
        start_time = time.perf_counter()

        imu_config = _imu_config_for_event_run(cfg, sequence)
        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        event_trajectory = EventVoBackend().run(sequence, config=cfg.event_vo_config)

        return fuse_imu_and_visual(
            imu_trajectory=imu_trajectory,
            visual_trajectory=event_trajectory,
            visual_correction_gain=cfg.event_correction_gain,
            min_visual_confidence_for_correction=cfg.min_event_confidence_for_correction,
            ok_confidence_threshold=cfg.ok_confidence_threshold,
            degraded_confidence_threshold=cfg.degraded_confidence_threshold,
            method=self.method,
            base_imu_confidence=0.35,
            visual_confidence_weight=0.65,
            start_time=start_time,
        )
