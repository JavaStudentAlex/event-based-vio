import time
from dataclasses import dataclass, field

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.baselines.common import (
    fuse_imu_and_visual,
)
from nav_benchmark.baselines.event_imu import _default_imu_config_from_sequence
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.baselines.visual import FeatureVoConfig, RgbVoBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import Trajectory


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
        start_time = time.perf_counter()
        if config is None:
            config = ImageImuConfig()

        if config.imu_config is None:  # noqa: SIM108
            imu_config = _default_imu_config_from_sequence(sequence)
        else:
            imu_config = config.imu_config

        imu_trajectory = ImuOnlyBackend().run(sequence, config=imu_config)
        rgb_trajectory = RgbVoBackend().run(sequence, config=config.rgb_vo_config)

        fused_trajectory = fuse_imu_and_visual(
            imu_trajectory=imu_trajectory,
            visual_trajectory=rgb_trajectory,
            visual_correction_gain=config.image_correction_gain,
            min_visual_confidence_for_correction=config.min_image_confidence_for_correction,
            ok_confidence_threshold=config.ok_confidence_threshold,
            degraded_confidence_threshold=config.degraded_confidence_threshold,
            method=self.method,
            base_imu_confidence=0.40,
            visual_confidence_weight=0.60,
            start_time=start_time,
        )
        return fused_trajectory
