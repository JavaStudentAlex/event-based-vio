"""Episodic environment for learning per-backend trust over the gated EKF.

The interface is gymnasium-style (``reset``/``step``) without the dependency.
Actions are per-backend trust values in ``[0, 1]`` (method order = sorted
backend names). The reward is the per-control-step reduction of the absolute
position error against ground truth, minus a small penalty on trust jitter;
episode return therefore telescopes to (initial error - final error) plus
smoothness shaping. Everything is deterministic given the episode, the
perturbation list, and the action sequence.
"""

from dataclasses import dataclass, field

import numpy as np

from nav_benchmark.ensemble.rl_gated import GatedEkfFusionCore, RlGatedFusionConfig, _control_boundaries
from nav_benchmark.rl.episodes import FusionEpisode
from nav_benchmark.rl.features import FeatureConfig, build_observation, initial_observation, observation_dim
from nav_benchmark.rl.perturb import BackendPerturbation, apply_perturbations
from nav_benchmark.trajectory.models import Trajectory


@dataclass
class EnvConfig:
    """Reward shaping and fusion configuration for the training environment."""

    fusion: RlGatedFusionConfig = field(default_factory=RlGatedFusionConfig)
    jitter_penalty: float = 0.05
    reward_clip_m: float = 2.0


class EnsembleFusionEnv:
    """One fusion episode as an RL environment with trust-vector actions."""

    def __init__(
        self,
        episode: FusionEpisode,
        feature_config: FeatureConfig,
        *,
        config: EnvConfig | None = None,
        perturbations: list[BackendPerturbation] | None = None,
    ) -> None:
        self.episode = episode
        self.config = config if config is not None else EnvConfig()
        self.feature_config = feature_config
        methods = tuple(sorted(episode.backend_trajectories))
        if feature_config.methods != methods:
            raise ValueError(f"Feature layout methods {feature_config.methods} != episode methods {methods}")
        self.methods = methods
        applied = perturbations if perturbations is not None else []
        self._backends = {
            method: apply_perturbations(trajectory, applied)
            for method, trajectory in episode.backend_trajectories.items()
        }
        imu_t = np.asarray(episode.imu["t"], dtype=np.float64)
        boundaries = _control_boundaries(imu_t, self.config.fusion.control_period_sec)
        boundary_times = np.array([imu_t[last + 1] for _first, last in boundaries], dtype=np.float64)
        self._gt_at_boundaries = np.stack(
            [np.interp(boundary_times, episode.gt_timestamps, episode.gt_positions[:, axis]) for axis in range(3)],
            axis=1,
        )
        self._boundary_times = boundary_times
        self._core: GatedEkfFusionCore | None = None
        self._prev_trusts = np.ones(len(self.methods), dtype=np.float64)
        self._prev_error_m = 0.0
        self._done = False

    @property
    def action_dim(self) -> int:
        return len(self.methods)

    @property
    def observation_dim(self) -> int:
        return observation_dim(self.feature_config)

    @property
    def num_steps(self) -> int:
        return len(self._boundary_times)

    def reset(self) -> np.ndarray:
        self._core = GatedEkfFusionCore(
            self.episode.imu,
            self._backends,
            config=self.config.fusion,
            initial_position=self.episode.initial_position,
            initial_velocity=self.episode.initial_velocity,
            initial_orientation_xyzw=self.episode.initial_orientation_xyzw,
        )
        self._prev_trusts = np.ones(len(self.methods), dtype=np.float64)
        self._prev_error_m = float(np.linalg.norm(self.episode.initial_position - self.episode.gt_positions[0]))
        self._done = False
        return initial_observation(self.feature_config)

    def _reward(self, error_m: float, action: np.ndarray) -> float:
        improvement = self._prev_error_m - error_m
        jitter = float(np.mean((action - self._prev_trusts) ** 2))
        reward = improvement - self.config.jitter_penalty * jitter
        return float(np.clip(reward, -self.config.reward_clip_m, self.config.reward_clip_m))

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        if self._core is None:
            raise RuntimeError("Environment must be reset before stepping")
        if self._done:
            raise RuntimeError("Episode is done; call reset")
        action = np.clip(np.asarray(action, dtype=np.float64).reshape(-1), 0.0, 1.0)
        if action.size != self.action_dim:
            raise ValueError(f"Expected action of size {self.action_dim}, got {action.size}")

        summary = self._core.step(action)
        step_index = summary.index
        error_m = float(np.linalg.norm(self._core.state_position() - self._gt_at_boundaries[step_index]))
        reward = self._reward(error_m, action)
        self._prev_error_m = error_m
        self._prev_trusts = action.copy()
        self._done = step_index + 1 >= self.num_steps

        jepa_point = None
        if self.episode.jepa_series is not None:
            jepa_point = self.episode.jepa_series.at(summary.end_time)
        observation = build_observation(
            self.feature_config,
            summary,
            progress=(step_index + 1) / self.num_steps,
            prev_trusts=action,
            jepa_point=jepa_point,
        )
        info = {
            "position_error_m": error_m,
            "accepted_updates": {m: summary.stats[m].accepted for m in self.methods},
            "end_time": summary.end_time,
        }
        return observation, reward, self._done, info

    def result(self) -> tuple[Trajectory, list]:
        """Fused trajectory and update records once the episode has finished."""
        if self._core is None or not self._done:
            raise RuntimeError("Episode has not finished; result is undefined")
        return self._core.result()

    def final_position_error_m(self) -> float:
        if not self._done:
            raise RuntimeError("Episode has not finished")
        return self._prev_error_m
