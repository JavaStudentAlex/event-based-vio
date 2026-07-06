"""Fusion environment: determinism, reward semantics, and weighted-EKF parity."""

import numpy as np
import pytest

from nav_benchmark.datasets.mvsec import IMU_DTYPE
from nav_benchmark.ensemble.fusion import run_weighted_ekf_fusion
from nav_benchmark.ensemble.rl_gated import RlGatedFusionConfig
from nav_benchmark.rl.env import EnsembleFusionEnv, EnvConfig
from nav_benchmark.rl.episodes import FusionEpisode
from nav_benchmark.rl.features import FeatureConfig, JepaObsSeries, feature_names
from nav_benchmark.rl.perturb import KIND_CONFIDENT_BIAS, BackendPerturbation
from nav_benchmark.trajectory.models import Trajectory

_METHODS = ("event_vo", "rgb_vo")


def _static_imu(count: int = 101, dt: float = 0.01) -> np.ndarray:
    imu = np.empty(count, dtype=IMU_DTYPE)
    imu["t"] = np.arange(count) * dt
    imu["ax"] = 0.0
    imu["ay"] = 0.0
    imu["az"] = 9.81
    imu["gx"] = 0.0
    imu["gy"] = 0.0
    imu["gz"] = 0.0
    return imu


def _measurement_trajectory(method: str, timestamps: np.ndarray, positions: np.ndarray) -> Trajectory:
    count = len(timestamps)
    orientations = np.zeros((count, 4))
    orientations[:, 3] = 1.0
    return Trajectory(
        timestamps=np.asarray(timestamps, dtype=np.float64),
        method=method,
        positions=np.asarray(positions, dtype=np.float64),
        orientations=orientations,
        confidence=np.full(count, 0.9),
        health=np.array(["OK"] * count, dtype=object),
    )


def _episode(jepa_series: JepaObsSeries | None = None) -> FusionEpisode:
    imu = _static_imu()
    meas_t = np.arange(0.1, 1.01, 0.1)
    zeros = np.zeros((len(meas_t), 3))
    backends = {
        "event_vo": _measurement_trajectory("event_vo", meas_t, zeros),
        "rgb_vo": _measurement_trajectory("rgb_vo", meas_t, zeros),
    }
    t = np.asarray(imu["t"], dtype=np.float64)
    return FusionEpisode(
        name="unit",
        t_start=float(t[0]),
        t_end=float(t[-1]),
        imu=imu,
        backend_trajectories=backends,
        initial_position=np.zeros(3),
        initial_velocity=np.zeros(3),
        initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
        gt_timestamps=t,
        gt_positions=np.zeros((len(t), 3)),
        jepa_series=jepa_series,
    )


def _env(episode=None, perturbations=None, jitter_penalty=0.05) -> EnsembleFusionEnv:
    config = EnvConfig(fusion=RlGatedFusionConfig(), jitter_penalty=jitter_penalty)
    config.fusion.base.chi2_threshold = 1e9  # keep gates out of reward-sign experiments
    return EnsembleFusionEnv(
        episode if episode is not None else _episode(),
        FeatureConfig(methods=_METHODS),
        config=config,
        perturbations=perturbations or [],
    )


def _rollout(env: EnsembleFusionEnv, action_fn) -> tuple[float, list[np.ndarray]]:
    obs = env.reset()
    total = 0.0
    observations = [obs]
    done = False
    step = 0
    while not done:
        obs, reward, done, _info = env.step(action_fn(step, obs))
        observations.append(obs)
        total += reward
        step += 1
    return total, observations


class TestEnvBasics:
    def test_shapes_and_step_count(self):
        env = _env()
        assert env.action_dim == 2
        obs = env.reset()
        assert obs.shape == (env.observation_dim,)
        assert env.num_steps == 10  # 1 s at 100 ms control period

    def test_deterministic_given_actions(self):
        actions = lambda step, _obs: np.array([0.7, 0.3 + 0.05 * (step % 3)])  # noqa: E731
        return_a, obs_a = _rollout(_env(), actions)
        return_b, obs_b = _rollout(_env(), actions)
        assert return_a == return_b
        for a, b in zip(obs_a, obs_b, strict=True):
            np.testing.assert_array_equal(a, b)

    def test_step_contracts(self):
        env = _env()
        with pytest.raises(RuntimeError, match="reset"):
            env.step(np.ones(2))
        env.reset()
        with pytest.raises(ValueError, match="size"):
            env.step(np.ones(3))
        with pytest.raises(RuntimeError, match="not finished"):
            env.result()


class TestRewardSemantics:
    def test_distrusting_a_lying_backend_earns_more_return(self):
        lie = BackendPerturbation(
            method="rgb_vo", kind=KIND_CONFIDENT_BIAS, t_start=0.2, t_end=1.0, magnitude_m=3.0, seed=1
        )
        naive_return, _ = _rollout(_env(perturbations=[lie], jitter_penalty=0.0), lambda *_: np.ones(2))
        informed_return, _ = _rollout(_env(perturbations=[lie], jitter_penalty=0.0), lambda *_: np.array([1.0, 0.0]))
        assert informed_return > naive_return

    def test_jitter_penalty_punishes_oscillation(self):
        flip = lambda step, _obs: np.array([1.0, 1.0]) if step % 2 == 0 else np.array([0.0, 0.0])  # noqa: E731
        smooth_return, _ = _rollout(_env(jitter_penalty=0.5), lambda *_: np.ones(2))
        flappy_return, _ = _rollout(_env(jitter_penalty=0.5), flip)
        assert smooth_return > flappy_return

    def test_final_error_matches_info(self):
        env = _env()
        env.reset()
        done = False
        while not done:
            _obs, _reward, done, info = env.step(np.ones(2))
        assert env.final_position_error_m() == pytest.approx(info["position_error_m"])


class TestParityAndJepa:
    def test_all_ones_rollout_equals_weighted_ekf(self):
        episode = _episode()
        env = EnsembleFusionEnv(episode, FeatureConfig(methods=_METHODS))
        env.reset()
        done = False
        while not done:
            _obs, _reward, done, _info = env.step(np.ones(2))
        trajectory, _records = env.result()

        reference, _ = run_weighted_ekf_fusion(
            episode.imu,
            episode.backend_trajectories,
            initial_position=episode.initial_position,
            initial_velocity=episode.initial_velocity,
            initial_orientation_xyzw=episode.initial_orientation_xyzw,
        )
        np.testing.assert_allclose(trajectory.positions, reference.positions, atol=0.0)

    def test_jepa_series_reaches_observation(self):
        series = JepaObsSeries(
            times=np.array([0.05]),
            rgb_surprise=np.array([0.9]),
            event_surprise=np.array([0.7]),
            embedding_speed=np.array([0.4]),
        )
        env = EnsembleFusionEnv(_episode(jepa_series=series), FeatureConfig(methods=_METHODS, include_jepa=True))
        env.reset()
        obs, _reward, _done, _info = env.step(np.ones(2))
        names = feature_names(env.feature_config)
        assert obs[names.index("jepa.rgb_surprise")] == pytest.approx(np.tanh(0.9))
        assert obs[names.index("jepa.event_surprise")] == pytest.approx(np.tanh(0.7))
