"""Seeded backend perturbations: kind semantics, determinism, sampler contracts."""

import numpy as np
import pytest

from nav_benchmark.rl.perturb import (
    KIND_BIAS_RAMP,
    KIND_CONFIDENT_BIAS,
    KIND_DROPOUT,
    KIND_NOISE_BURST,
    BackendPerturbation,
    apply_perturbations,
    sample_episode_perturbations,
)
from nav_benchmark.trajectory.models import PoseHealth, Trajectory


def _trajectory(method: str = "rgb_vo", count: int = 11) -> Trajectory:
    t = np.linspace(0.0, 1.0, count)
    orientations = np.zeros((count, 4))
    orientations[:, 3] = 1.0
    return Trajectory(
        timestamps=t,
        method=method,
        positions=np.zeros((count, 3)),
        orientations=orientations,
        confidence=np.full(count, 0.9),
        health=np.array([PoseHealth.OK.value] * count, dtype=object),
    )


def _one(kind: str, magnitude: float = 1.0, seed: int = 3) -> BackendPerturbation:
    return BackendPerturbation(method="rgb_vo", kind=kind, t_start=0.4, t_end=0.8, magnitude_m=magnitude, seed=seed)


class TestApplyPerturbations:
    def test_dropout_marks_lost_and_zeroes_confidence(self):
        result = apply_perturbations(_trajectory(), [_one(KIND_DROPOUT)])
        window = (result.timestamps >= 0.4) & (result.timestamps <= 0.8)
        assert all(h == PoseHealth.LOST.value for h in result.health[window])
        np.testing.assert_allclose(result.confidence[window], 0.0)
        assert all(h == PoseHealth.OK.value for h in result.health[~window])

    def test_bias_ramp_shifts_positions_and_lowers_confidence(self):
        result = apply_perturbations(_trajectory(), [_one(KIND_BIAS_RAMP, magnitude=2.0)])
        window = (result.timestamps >= 0.4) & (result.timestamps <= 0.8)
        offsets = np.linalg.norm(result.positions[window], axis=1)
        assert offsets[-1] == pytest.approx(2.0)
        assert np.all(np.diff(offsets) >= 0.0)
        assert np.all(result.confidence[window] < 0.9)

    def test_confident_bias_keeps_confidence(self):
        result = apply_perturbations(_trajectory(), [_one(KIND_CONFIDENT_BIAS, magnitude=2.0)])
        window = (result.timestamps >= 0.4) & (result.timestamps <= 0.8)
        assert np.linalg.norm(result.positions[window][-1]) == pytest.approx(2.0)
        np.testing.assert_allclose(result.confidence, 0.9)

    def test_noise_burst_is_seed_deterministic(self):
        a = apply_perturbations(_trajectory(), [_one(KIND_NOISE_BURST, magnitude=0.5, seed=7)])
        b = apply_perturbations(_trajectory(), [_one(KIND_NOISE_BURST, magnitude=0.5, seed=7)])
        c = apply_perturbations(_trajectory(), [_one(KIND_NOISE_BURST, magnitude=0.5, seed=8)])
        np.testing.assert_array_equal(a.positions, b.positions)
        assert not np.array_equal(a.positions, c.positions)

    def test_other_methods_are_untouched_and_source_is_never_mutated(self):
        source = _trajectory()
        result = apply_perturbations(source, [_one(KIND_BIAS_RAMP, magnitude=2.0)])
        np.testing.assert_allclose(source.positions, 0.0)
        other = apply_perturbations(_trajectory(method="event_vo"), [_one(KIND_BIAS_RAMP)])
        np.testing.assert_allclose(other.positions, 0.0)
        assert result is not source

    def test_invalid_specs_are_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            BackendPerturbation(method="rgb_vo", kind="teleport", t_start=0.0, t_end=1.0, magnitude_m=1.0)
        with pytest.raises(ValueError, match="duration"):
            BackendPerturbation(method="rgb_vo", kind=KIND_DROPOUT, t_start=1.0, t_end=1.0, magnitude_m=1.0)


class TestSampler:
    def test_severity_zero_is_clean(self):
        rng = np.random.Generator(np.random.PCG64(0))
        assert sample_episode_perturbations(rng, ("rgb_vo",), 0.0, 1.0, 0) == []

    def test_sampler_is_seed_deterministic_and_in_bounds(self):
        methods = ("event_vo", "rgb_vo")
        first = sample_episode_perturbations(np.random.Generator(np.random.PCG64(5)), methods, 2.0, 10.0, 3)
        second = sample_episode_perturbations(np.random.Generator(np.random.PCG64(5)), methods, 2.0, 10.0, 3)
        assert first == second
        assert len(first) == 3
        for perturbation in first:
            assert perturbation.method in methods
            assert 2.0 <= perturbation.t_start < perturbation.t_end <= 10.0
