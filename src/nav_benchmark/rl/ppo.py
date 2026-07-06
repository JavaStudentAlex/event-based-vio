"""PPO agent (torch) producing per-backend trust actions in ``[0, 1]``.

The policy is a diagonal Gaussian in pre-squash space; actions are the sigmoid
of the sampled pre-squash vector. PPO ratios use the Gaussian log-density of
the stored pre-squash sample, where the (action-fixed) sigmoid Jacobian
cancels between old and new policies. Exploration noise and minibatch
shuffling come from a caller-provided numpy generator, so training is
reproducible on CPU regardless of global torch RNG state. Checkpoints embed
the observation-layout metadata so inference can refuse mismatched features.
"""

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from nav_benchmark.learn.torch_utils import resolve_device

CHECKPOINT_VERSION = 1
_LOG_STD_MIN = -4.0
_LOG_STD_MAX = 1.0


@dataclass
class PpoConfig:
    """Network and optimisation hyperparameters for the gating policy."""

    obs_dim: int
    act_dim: int
    hidden: tuple[int, ...] = (64, 64)
    lr: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_ratio: float = 0.2
    update_epochs: int = 8
    minibatch_size: int = 64
    entropy_coef: float = 1e-3
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    init_log_std: float = -0.5
    seed: int = 0


def _mlp(sizes: list[int], final_gain: float) -> nn.Sequential:
    layers: list[nn.Module] = []
    for i in range(len(sizes) - 1):
        linear = nn.Linear(sizes[i], sizes[i + 1])
        last = i == len(sizes) - 2
        nn.init.orthogonal_(linear.weight, gain=final_gain if last else math.sqrt(2.0))
        nn.init.zeros_(linear.bias)
        layers.append(linear)
        if not last:
            layers.append(nn.Tanh())
    return nn.Sequential(*layers)


class PolicyValueNet(nn.Module):
    """Separate policy and value MLPs with a state-independent log-std vector."""

    def __init__(self, config: PpoConfig) -> None:
        super().__init__()
        sizes = [config.obs_dim, *config.hidden]
        self.policy = _mlp([*sizes, config.act_dim], final_gain=0.01)
        self.value = _mlp([*sizes, 1], final_gain=1.0)
        self.log_std = nn.Parameter(torch.full((config.act_dim,), float(config.init_log_std)))

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mean = self.policy(obs)
        log_std = torch.clamp(self.log_std, _LOG_STD_MIN, _LOG_STD_MAX)
        return mean, log_std, self.value(obs).squeeze(-1)


def _gaussian_log_prob(u: torch.Tensor, mean: torch.Tensor, log_std: torch.Tensor) -> torch.Tensor:
    var = torch.exp(2.0 * log_std)
    per_dim = -0.5 * (u - mean) ** 2 / var - log_std - 0.5 * math.log(2.0 * math.pi)
    return per_dim.sum(dim=-1)


class RunningNorm:
    """Running mean/variance observation normalizer (frozen at inference)."""

    def __init__(self, dim: int) -> None:
        self.mean = np.zeros(dim, dtype=np.float64)
        self.var = np.ones(dim, dtype=np.float64)
        self.count = 1e-4

    def update(self, batch: np.ndarray) -> None:
        batch = np.atleast_2d(np.asarray(batch, dtype=np.float64))
        batch_mean = batch.mean(axis=0)
        batch_var = batch.var(axis=0)
        batch_count = batch.shape[0]
        delta = batch_mean - self.mean
        total = self.count + batch_count
        new_mean = self.mean + delta * batch_count / total
        m_a = self.var * self.count
        m_b = batch_var * batch_count
        m2 = m_a + m_b + delta**2 * self.count * batch_count / total
        self.mean, self.var, self.count = new_mean, m2 / total, total

    def normalize(self, obs: np.ndarray) -> np.ndarray:
        return (np.asarray(obs, dtype=np.float64) - self.mean) / np.sqrt(self.var + 1e-8)

    def state(self) -> dict[str, Any]:
        return {"mean": self.mean.tolist(), "var": self.var.tolist(), "count": float(self.count)}

    @staticmethod
    def from_state(state: dict[str, Any]) -> "RunningNorm":
        norm = RunningNorm(len(state["mean"]))
        norm.mean = np.asarray(state["mean"], dtype=np.float64)
        norm.var = np.asarray(state["var"], dtype=np.float64)
        norm.count = float(state["count"])
        return norm


@dataclass
class RolloutBuffer:
    """Complete-episode transitions collected between PPO updates."""

    obs: list[np.ndarray] = field(default_factory=list)
    pre_squash: list[np.ndarray] = field(default_factory=list)
    log_probs: list[float] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    dones: list[bool] = field(default_factory=list)

    def add(self, obs: np.ndarray, u: np.ndarray, log_prob: float, value: float, reward: float, done: bool) -> None:
        self.obs.append(np.asarray(obs, dtype=np.float64))
        self.pre_squash.append(np.asarray(u, dtype=np.float64))
        self.log_probs.append(float(log_prob))
        self.values.append(float(value))
        self.rewards.append(float(reward))
        self.dones.append(bool(done))

    def __len__(self) -> int:
        return len(self.rewards)

    def compute_gae(self, gamma: float, lam: float) -> tuple[np.ndarray, np.ndarray]:
        if not self.dones or not self.dones[-1]:
            raise ValueError("Rollout buffers must end on an episode boundary")
        count = len(self.rewards)
        advantages = np.zeros(count, dtype=np.float64)
        last_advantage = 0.0
        for t in reversed(range(count)):
            next_value = 0.0 if self.dones[t] else self.values[t + 1]
            non_terminal = 0.0 if self.dones[t] else 1.0
            delta = self.rewards[t] + gamma * next_value - self.values[t]
            last_advantage = delta + gamma * lam * non_terminal * last_advantage
            advantages[t] = last_advantage
        returns = advantages + np.asarray(self.values, dtype=np.float64)
        return advantages, returns


class PpoAgent:
    """PPO with sigmoid-squashed Gaussian actions and checkpointed obs layout."""

    def __init__(
        self,
        config: PpoConfig,
        *,
        feature_metadata: dict[str, Any] | None = None,
        device: str = "cpu",
    ) -> None:
        self.config = config
        self.device = resolve_device(device)
        self.feature_metadata = feature_metadata or {}
        self.extra_metadata: dict[str, Any] = {}
        torch.manual_seed(config.seed)
        self.net = PolicyValueNet(config).to(self.device)
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=config.lr)
        self.normalizer = RunningNorm(config.obs_dim)

    def _forward_numpy(self, obs_normalized: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        tensor = torch.as_tensor(obs_normalized, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            mean, log_std, value = self.net(tensor)
        return (
            mean.squeeze(0).cpu().numpy().astype(np.float64),
            log_std.cpu().numpy().astype(np.float64),
            float(value.item()),
        )

    def act(self, obs: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
        """Sample an action; returns (action, normalized_obs, pre_squash, log_prob, value).

        ``log_prob`` is the Gaussian density of the pre-squash sample; the
        sigmoid Jacobian is omitted because it cancels in PPO ratios.
        """
        self.normalizer.update(obs)
        obs_normalized = self.normalizer.normalize(obs)
        mean, log_std, value = self._forward_numpy(obs_normalized)
        noise = rng.standard_normal(self.config.act_dim)
        u = mean + np.exp(log_std) * noise
        action = 1.0 / (1.0 + np.exp(-u))
        var = np.exp(2.0 * log_std)
        log_prob = float(np.sum(-0.5 * (u - mean) ** 2 / var - log_std - 0.5 * math.log(2.0 * math.pi)))
        return action, obs_normalized, u, log_prob, value

    def act_deterministic(self, obs: np.ndarray) -> np.ndarray:
        """Mode action for evaluation/inference (no exploration, frozen normalizer)."""
        obs_normalized = self.normalizer.normalize(obs)
        mean, _log_std, _value = self._forward_numpy(obs_normalized)
        return 1.0 / (1.0 + np.exp(-mean))

    def _minibatch_indices(self, count: int, rng: np.random.Generator) -> list[np.ndarray]:
        order = rng.permutation(count)
        size = min(self.config.minibatch_size, count)
        return [order[start : start + size] for start in range(0, count, size)]

    def update(self, buffer: RolloutBuffer, rng: np.random.Generator) -> dict[str, float]:
        """One PPO update over a buffer of complete episodes."""
        advantages, returns = buffer.compute_gae(self.config.gamma, self.config.gae_lambda)
        obs = torch.as_tensor(np.stack(buffer.obs), dtype=torch.float32, device=self.device)
        pre_squash = torch.as_tensor(np.stack(buffer.pre_squash), dtype=torch.float32, device=self.device)
        old_log_probs = torch.as_tensor(np.asarray(buffer.log_probs), dtype=torch.float32, device=self.device)
        adv_tensor = torch.as_tensor(advantages, dtype=torch.float32, device=self.device)
        adv_tensor = (adv_tensor - adv_tensor.mean()) / (adv_tensor.std() + 1e-8)
        returns_tensor = torch.as_tensor(returns, dtype=torch.float32, device=self.device)

        stats = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "approx_kl": 0.0, "clip_frac": 0.0}
        batches = 0
        for _epoch in range(self.config.update_epochs):
            for indices in self._minibatch_indices(len(buffer), rng):
                idx = torch.as_tensor(indices, dtype=torch.long, device=self.device)
                batch_stats = self._update_minibatch(
                    obs[idx], pre_squash[idx], old_log_probs[idx], adv_tensor[idx], returns_tensor[idx]
                )
                for key in stats:
                    stats[key] += batch_stats[key]
                batches += 1
        return {key: value / max(batches, 1) for key, value in stats.items()}

    def _update_minibatch(
        self,
        obs: torch.Tensor,
        pre_squash: torch.Tensor,
        old_log_probs: torch.Tensor,
        advantages: torch.Tensor,
        returns: torch.Tensor,
    ) -> dict[str, float]:
        mean, log_std, values = self.net(obs)
        log_probs = _gaussian_log_prob(pre_squash, mean, log_std)
        ratio = torch.exp(log_probs - old_log_probs)
        clipped = torch.clamp(ratio, 1.0 - self.config.clip_ratio, 1.0 + self.config.clip_ratio)
        policy_loss = -torch.min(ratio * advantages, clipped * advantages).mean()
        value_loss = 0.5 * ((values - returns) ** 2).mean()
        entropy = (log_std + 0.5 * math.log(2.0 * math.pi * math.e)).sum()
        loss = policy_loss + self.config.value_coef * value_loss - self.config.entropy_coef * entropy

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.net.parameters(), self.config.max_grad_norm)
        self.optimizer.step()

        with torch.no_grad():
            approx_kl = (old_log_probs - log_probs).mean()
            clip_frac = ((ratio - 1.0).abs() > self.config.clip_ratio).float().mean()
        return {
            "policy_loss": float(policy_loss.item()),
            "value_loss": float(value_loss.item()),
            "entropy": float(entropy.item()),
            "approx_kl": float(approx_kl.item()),
            "clip_frac": float(clip_frac.item()),
        }

    def value_estimate(self, obs: np.ndarray) -> float:
        obs_normalized = self.normalizer.normalize(obs)
        _mean, _log_std, value = self._forward_numpy(obs_normalized)
        return value

    def save(self, path: str | Path, *, extra_metadata: dict[str, Any] | None = None) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CHECKPOINT_VERSION,
            "config": asdict(self.config),
            "feature_metadata": self.feature_metadata,
            "extra_metadata": extra_metadata or {},
            "net_state": {key: tensor.cpu() for key, tensor in self.net.state_dict().items()},
            "normalizer": self.normalizer.state(),
        }
        torch.save(payload, path)

    @staticmethod
    def load(path: str | Path, *, device: str = "cpu") -> "PpoAgent":
        payload = torch.load(Path(path), map_location="cpu", weights_only=True)
        if payload.get("version") != CHECKPOINT_VERSION:
            raise ValueError(f"Unsupported policy checkpoint version: {payload.get('version')!r}")
        config_dict = dict(payload["config"])
        config_dict["hidden"] = tuple(config_dict["hidden"])
        config = PpoConfig(**config_dict)
        agent = PpoAgent(config, feature_metadata=dict(payload["feature_metadata"]), device=device)
        agent.net.load_state_dict(payload["net_state"])
        agent.normalizer = RunningNorm.from_state(payload["normalizer"])
        agent.extra_metadata = dict(payload.get("extra_metadata", {}))
        return agent
