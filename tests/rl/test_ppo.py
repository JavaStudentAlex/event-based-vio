"""PPO agent: GAE math, learning on a toy task, checkpoint determinism."""

import numpy as np
import pytest
import torch

from nav_benchmark.rl.ppo import PpoAgent, PpoConfig, RolloutBuffer, RunningNorm


def _config(**overrides) -> PpoConfig:
    defaults = dict(
        obs_dim=2,
        act_dim=2,
        hidden=(16, 16),
        lr=3e-3,
        minibatch_size=32,
        update_epochs=4,
        entropy_coef=1e-4,
        seed=7,
    )
    defaults.update(overrides)
    return PpoConfig(**defaults)


class TestGae:
    def test_matches_hand_computed_values(self):
        buffer = RolloutBuffer()
        buffer.add(np.zeros(2), np.zeros(2), 0.0, 0.5, 1.0, False)
        buffer.add(np.zeros(2), np.zeros(2), 0.0, 0.5, 1.0, True)
        advantages, returns = buffer.compute_gae(gamma=0.5, lam=0.5)
        # t=1: delta = 1 - 0.5 = 0.5 -> adv 0.5
        # t=0: delta = 1 + 0.5*0.5 - 0.5 = 0.75 -> adv 0.75 + 0.25*0.5 = 0.875
        np.testing.assert_allclose(advantages, [0.875, 0.5])
        np.testing.assert_allclose(returns, [1.375, 1.0])

    def test_requires_terminal_final_transition(self):
        buffer = RolloutBuffer()
        buffer.add(np.zeros(2), np.zeros(2), 0.0, 0.5, 1.0, False)
        with pytest.raises(ValueError, match="episode boundary"):
            buffer.compute_gae(gamma=0.9, lam=0.9)


class TestRunningNorm:
    def test_tracks_mean_and_variance(self):
        norm = RunningNorm(1)
        rng = np.random.Generator(np.random.PCG64(0))
        data = rng.normal(3.0, 2.0, size=(500, 1))
        for row in data:
            norm.update(row)
        assert norm.mean[0] == pytest.approx(3.0, abs=0.3)
        assert np.sqrt(norm.var[0]) == pytest.approx(2.0, abs=0.3)
        roundtrip = RunningNorm.from_state(norm.state())
        np.testing.assert_allclose(roundtrip.normalize(np.array([5.0])), norm.normalize(np.array([5.0])))


class TestLearning:
    def test_ppo_learns_to_raise_trust_on_a_toy_task(self):
        """One-step episodes, reward = mean(action): optimum is full trust everywhere."""
        agent = PpoAgent(_config())
        rng = np.random.Generator(np.random.PCG64(3))
        obs = np.array([1.0, -1.0])

        def iteration_return() -> float:
            buffer = RolloutBuffer()
            rewards = []
            for _ in range(64):
                action, obs_n, u, logp, value = agent.act(obs, rng)
                reward = float(np.mean(action))
                buffer.add(obs_n, u, logp, value, reward, True)
                rewards.append(reward)
            agent.update(buffer, rng)
            return float(np.mean(rewards))

        first = iteration_return()
        for _ in range(11):
            last = iteration_return()

        assert last > first + 0.15
        assert float(np.mean(agent.act_deterministic(obs))) > 0.8

    def test_same_seed_is_bit_deterministic_on_cpu(self):
        results = []
        for _attempt in range(2):
            agent = PpoAgent(_config())
            rng = np.random.Generator(np.random.PCG64(11))
            buffer = RolloutBuffer()
            for _ in range(16):
                action, obs_n, u, logp, value = agent.act(np.array([0.3, 0.6]), rng)
                buffer.add(obs_n, u, logp, value, float(action.sum()), True)
            agent.update(buffer, rng)
            results.append(agent.act_deterministic(np.array([0.3, 0.6])))
        np.testing.assert_array_equal(results[0], results[1])


class TestCheckpoint:
    def test_roundtrip_preserves_behavior_and_metadata(self, tmp_path):
        metadata = {"version": 1, "features": {"methods": ["a", "b"]}, "control_period_sec": 0.1}
        agent = PpoAgent(_config(), feature_metadata=metadata)
        agent.normalizer.update(np.array([[0.5, 2.0], [1.5, -1.0]]))
        observation = np.array([0.2, 0.4])
        expected = agent.act_deterministic(observation)

        path = tmp_path / "policy.pt"
        agent.save(path, extra_metadata={"iteration": 3})
        restored = PpoAgent.load(path)

        np.testing.assert_allclose(restored.act_deterministic(observation), expected, rtol=0, atol=0)
        assert restored.feature_metadata == metadata
        assert restored.extra_metadata["iteration"] == 3

    def test_rejects_unknown_version(self, tmp_path):
        agent = PpoAgent(_config())
        path = tmp_path / "policy.pt"
        agent.save(path)
        payload = torch.load(path, weights_only=True)
        payload["version"] = 999
        torch.save(payload, path)
        with pytest.raises(ValueError, match="version"):
            PpoAgent.load(path)
