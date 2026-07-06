"""Episode construction: windowing, rebasing, ground-truth sampling."""

import numpy as np
import pytest

from nav_benchmark.baselines.imu import ImuOnlyConfig
from nav_benchmark.datasets.mvsec import IMU_DTYPE, POSE_DTYPE
from nav_benchmark.rl.episodes import EnsembleInputs, build_episodes
from nav_benchmark.trajectory.models import Trajectory


def _imu(count: int = 201, dt: float = 0.01) -> np.ndarray:
    imu = np.empty(count, dtype=IMU_DTYPE)
    imu["t"] = np.arange(count) * dt
    for name in ("ax", "ay", "gx", "gy", "gz"):
        imu[name] = 0.0
    imu["az"] = 9.81
    return imu


def _gt_line(count: int = 21, dt: float = 0.1, speed: float = 1.0) -> np.ndarray:
    poses = np.zeros(count, dtype=POSE_DTYPE)
    poses["t"] = np.arange(count) * dt
    poses["x"] = speed * poses["t"]
    poses["qw"] = 1.0
    return poses


def _backend(method: str, offset: float) -> Trajectory:
    t = np.arange(0.0, 2.01, 0.1)
    positions = np.zeros((len(t), 3))
    positions[:, 0] = t + offset  # follows GT with a constant bias
    orientations = np.zeros((len(t), 4))
    orientations[:, 3] = 1.0
    return Trajectory(
        timestamps=t,
        method=method,
        positions=positions,
        orientations=orientations,
        confidence=np.full(len(t), 0.9),
        health=np.array(["OK"] * len(t), dtype=object),
    )


def _inputs() -> EnsembleInputs:
    return EnsembleInputs(
        imu=_imu(),
        backend_trajectories={
            "event_vo": _backend("event_vo", offset=0.5),
            "rgb_vo": _backend("rgb_vo", offset=-0.25),
        },
        imu_config=ImuOnlyConfig(),
        gt_poses=_gt_line(),
    )


class TestBuildEpisodes:
    def test_windowing_covers_span_with_stride(self):
        episodes = build_episodes(_inputs(), window_sec=1.0, stride_sec=0.5, name_prefix="seq")
        assert len(episodes) == 3  # starts at 0.0, 0.5, 1.0 over a 2 s span
        assert episodes[0].t_start == pytest.approx(0.0)
        assert episodes[1].t_start == pytest.approx(0.5)
        assert all(ep.t_end - ep.t_start == pytest.approx(1.0) for ep in episodes)

    def test_short_span_yields_single_full_episode(self):
        episodes = build_episodes(_inputs(), window_sec=10.0, stride_sec=5.0, name_prefix="seq")
        assert len(episodes) == 1
        assert episodes[0].t_end == pytest.approx(2.0)

    def test_rebasing_anchors_backends_to_ground_truth_at_window_start(self):
        episodes = build_episodes(_inputs(), window_sec=1.0, stride_sec=0.5, name_prefix="seq")
        window = episodes[1]  # starts at t0=0.5 where GT x = 0.5
        for trajectory in window.backend_trajectories.values():
            first_time = trajectory.timestamps[0]
            expected_x = first_time  # rebased stream must sit on the GT line
            assert trajectory.positions[0, 0] == pytest.approx(expected_x, abs=1e-9)

    def test_initialization_comes_from_ground_truth(self):
        episodes = build_episodes(_inputs(), window_sec=1.0, stride_sec=0.5, name_prefix="seq")
        window = episodes[1]
        assert window.initial_position[0] == pytest.approx(0.5)
        assert window.initial_velocity[0] == pytest.approx(1.0, rel=1e-6)
        assert window.gt_positions.shape == (len(window.gt_timestamps), 3)
        np.testing.assert_allclose(window.gt_positions[:, 0], window.gt_timestamps, atol=1e-9)

    def test_invalid_parameters_are_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            build_episodes(_inputs(), window_sec=0.0, stride_sec=0.5, name_prefix="seq")
