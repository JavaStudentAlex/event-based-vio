"""Observation layout: dimensions, bounds, JEPA slots, and layout validation."""

import numpy as np
import pytest

from nav_benchmark.ensemble.rl_gated import ControlStepSummary, MethodWindowStats
from nav_benchmark.rl.features import (
    GLOBAL_FEATURES,
    JEPA_FEATURES,
    PER_METHOD_FEATURES,
    FeatureConfig,
    JepaObsSeries,
    build_observation,
    feature_names,
    initial_observation,
    observation_dim,
)

_METHODS = ("event_vo", "rgb_vo")


def _summary() -> ControlStepSummary:
    stats = {
        "event_vo": MethodWindowStats(
            offered=2, accepted=2, confidence_sum=1.8, innovation_sum_m=0.4, innovation_count=2
        ),
        "rgb_vo": MethodWindowStats(offered=1, accepted=0, confidence_sum=0.5, degraded=1, d2_sum=30.0, d2_count=1),
    }
    return ControlStepSummary(
        index=0,
        start_time=0.0,
        end_time=0.1,
        stats=stats,
        last_accept_age_sec={"event_vo": 0.05, "rgb_vo": 9.0},
        ekf_position_sigma_m=0.4,
        ekf_speed_mps=3.0,
        applied_trust={"event_vo": 1.0, "rgb_vo": 1.0},
    )


class TestLayout:
    def test_dimension_and_names_match(self):
        config = FeatureConfig(methods=_METHODS)
        names = feature_names(config)
        assert observation_dim(config) == len(names)
        assert len(names) == len(_METHODS) * len(PER_METHOD_FEATURES) + len(GLOBAL_FEATURES)

    def test_jepa_adds_exactly_its_slots(self):
        base = FeatureConfig(methods=_METHODS)
        jepa = FeatureConfig(methods=_METHODS, include_jepa=True)
        assert observation_dim(jepa) - observation_dim(base) == len(JEPA_FEATURES)
        assert feature_names(jepa)[-3:] == [f"jepa.{name}" for name in JEPA_FEATURES]

    def test_methods_must_be_sorted(self):
        with pytest.raises(ValueError, match="sorted"):
            FeatureConfig(methods=("rgb_vo", "event_vo"))

    def test_metadata_roundtrip(self):
        config = FeatureConfig(methods=_METHODS, include_jepa=True, innovation_scale_m=3.0)
        assert FeatureConfig.from_metadata(config.to_metadata()) == config


class TestBuildObservation:
    def test_values_are_bounded_and_causal_layout_is_stable(self):
        config = FeatureConfig(methods=_METHODS)
        obs = build_observation(config, _summary(), progress=0.5, prev_trusts=np.array([1.0, 0.5]))
        assert obs.shape == (observation_dim(config),)
        assert np.all(obs >= -1.0) and np.all(obs <= 1.0)
        names = feature_names(config)
        staleness_rgb = obs[names.index("rgb_vo.staleness")]
        assert staleness_rgb == pytest.approx(1.0)  # 9 s > 5 s horizon, saturated
        assert obs[names.index("event_vo.available")] == 1.0

    def test_initial_observation_defaults_to_full_prev_trust(self):
        config = FeatureConfig(methods=_METHODS)
        obs = initial_observation(config)
        names = feature_names(config)
        assert obs[names.index("global.prev_mean_trust")] == 1.0
        assert np.count_nonzero(obs) == 1

    def test_method_mismatch_is_rejected(self):
        config = FeatureConfig(methods=("event_imu", "event_vo", "rgb_vo"))
        with pytest.raises(ValueError, match="do not match"):
            build_observation(config, _summary(), progress=0.0, prev_trusts=np.ones(3))

    def test_jepa_point_fills_last_slots(self):
        config = FeatureConfig(methods=_METHODS, include_jepa=True)
        obs = build_observation(
            config, _summary(), progress=0.0, prev_trusts=np.ones(2), jepa_point=np.array([0.5, 0.2, 0.1])
        )
        np.testing.assert_allclose(obs[-3:], np.tanh([0.5, 0.2, 0.1]))
        missing = build_observation(config, _summary(), progress=0.0, prev_trusts=np.ones(2), jepa_point=None)
        np.testing.assert_allclose(missing[-3:], 0.0)


class TestJepaObsSeries:
    def test_at_is_causal(self):
        series = JepaObsSeries(
            times=np.array([1.0, 2.0]),
            rgb_surprise=np.array([0.1, 0.2]),
            event_surprise=np.array([0.3, 0.4]),
            embedding_speed=np.array([0.5, 0.6]),
        )
        np.testing.assert_allclose(series.at(0.5), [0.0, 0.0, 0.0])
        np.testing.assert_allclose(series.at(1.5), [0.1, 0.3, 0.5])
        np.testing.assert_allclose(series.at(2.5), [0.2, 0.4, 0.6])
