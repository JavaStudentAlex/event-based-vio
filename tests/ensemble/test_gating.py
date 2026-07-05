import numpy as np
import pytest

from nav_benchmark.ensemble.gating import (
    REASON_CONFIDENCE,
    REASON_HEALTH,
    REASON_MAHALANOBIS,
    REASON_MOTION_SANITY,
    REASON_TIMESTAMP,
    confidence_gate,
    confidence_to_position_sigma,
    health_confidence_multiplier,
    health_gate,
    mahalanobis_distance_squared,
    mahalanobis_gate,
    motion_sanity_gate,
    timestamp_gate,
)


class TestHealthGate:
    def test_ok_and_degraded_pass(self):
        assert health_gate("OK").accepted is True
        assert health_gate("OK").reason is None
        assert health_gate("DEGRADED").accepted is True

    def test_lost_and_invalid_reject(self):
        for label in ("LOST", "INVALID"):
            decision = health_gate(label)
            assert decision.accepted is False
            assert decision.reason == REASON_HEALTH


class TestConfidenceGate:
    def test_boundary_is_inclusive(self):
        assert confidence_gate(0.15, 0.15).accepted is True

    def test_below_floor_rejects(self):
        decision = confidence_gate(0.1499, 0.15)
        assert decision.accepted is False
        assert decision.reason == REASON_CONFIDENCE


class TestTimestampGate:
    def test_within_age_passes(self):
        assert timestamp_gate(10.0, 10.1, max_age_sec=0.1).accepted is True

    def test_stale_measurement_rejects(self):
        decision = timestamp_gate(10.0, 10.2, max_age_sec=0.1)
        assert decision.accepted is False
        assert decision.reason == REASON_TIMESTAMP

    def test_future_measurement_rejects(self):
        assert timestamp_gate(10.3, 10.0, max_age_sec=0.1).accepted is False


class TestMotionSanityGate:
    def test_plausible_speed_passes(self):
        assert motion_sanity_gate(position_jump_m=1.0, dt_sec=0.1, max_speed_mps=60.0).accepted is True

    def test_impossible_speed_rejects(self):
        decision = motion_sanity_gate(position_jump_m=10.0, dt_sec=0.1, max_speed_mps=60.0)
        assert decision.accepted is False
        assert decision.reason == REASON_MOTION_SANITY

    def test_tiny_dt_uses_floor(self):
        # dt floor of 1e-3 keeps the implied speed finite: 0.01 m / 1e-3 s = 10 m/s.
        assert motion_sanity_gate(position_jump_m=0.01, dt_sec=0.0, max_speed_mps=60.0).accepted is True
        assert motion_sanity_gate(position_jump_m=0.1, dt_sec=0.0, max_speed_mps=60.0).accepted is False


class TestMahalanobisGate:
    def test_distance_matches_analytic_value(self):
        innovation = np.array([2.0, 0.0, 0.0])
        S = np.eye(3) * 4.0
        assert mahalanobis_distance_squared(innovation, S) == pytest.approx(1.0)

    def test_rejects_artificial_outlier(self):
        # 10-sigma outlier on one axis: d2 = 100 with unit covariance.
        innovation = np.array([10.0, 0.0, 0.0])
        decision = mahalanobis_gate(innovation, np.eye(3), chi2_threshold=16.27)
        assert decision.accepted is False
        assert decision.reason == REASON_MAHALANOBIS

    def test_accepts_consistent_innovation(self):
        innovation = np.array([1.0, 1.0, 1.0])
        assert mahalanobis_gate(innovation, np.eye(3), chi2_threshold=16.27).accepted is True


class TestConfidenceToSigma:
    def test_extremes(self):
        assert confidence_to_position_sigma(1.0, sigma_min=0.05, sigma_range=5.0) == pytest.approx(0.05)
        assert confidence_to_position_sigma(0.0, sigma_min=0.05, sigma_range=5.0) == pytest.approx(5.05)

    def test_mapping_is_monotonically_decreasing_in_confidence(self):
        confidences = np.linspace(0.0, 1.0, 21)
        sigmas = [confidence_to_position_sigma(c, sigma_min=0.05, sigma_range=5.0) for c in confidences]
        diffs = np.diff(sigmas)
        assert np.all(diffs < 0.0)

    def test_out_of_range_confidence_is_clipped(self):
        assert confidence_to_position_sigma(1.7, 0.05, 5.0) == pytest.approx(0.05)
        assert confidence_to_position_sigma(-0.5, 0.05, 5.0) == pytest.approx(5.05)


class TestHealthConfidenceMultiplier:
    def test_values_per_health_state(self):
        assert health_confidence_multiplier("OK", 0.35) == 1.0
        assert health_confidence_multiplier("DEGRADED", 0.35) == 0.35
        assert health_confidence_multiplier("LOST", 0.35) == 0.0
        assert health_confidence_multiplier("INVALID", 0.35) == 0.0
