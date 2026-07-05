import csv

import numpy as np
import pytest

from nav_benchmark.datasets.mvsec import IMU_DTYPE
from nav_benchmark.ensemble.fusion import (
    EkfFusionConfig,
    WinnerTakesHealthyConfig,
    run_weighted_ekf_fusion,
    run_winner_takes_healthy,
    sample_backend_health,
    write_update_log_csv,
)
from nav_benchmark.trajectory.models import Trajectory


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


def _measurement_trajectory(
    method: str,
    timestamps: np.ndarray,
    positions: np.ndarray,
    *,
    confidence: float = 0.9,
    health: str = "OK",
) -> Trajectory:
    count = len(timestamps)
    orientations = np.zeros((count, 4))
    orientations[:, 3] = 1.0
    return Trajectory(
        timestamps=np.asarray(timestamps, dtype=np.float64),
        method=method,
        positions=np.asarray(positions, dtype=np.float64),
        orientations=orientations,
        confidence=np.full(count, confidence),
        health=np.array([health] * count, dtype=object),
    )


def _run_fusion(imu, backends, config=None):
    return run_weighted_ekf_fusion(
        imu,
        backends,
        config=config,
        initial_position=np.zeros(3),
        initial_velocity=np.zeros(3),
        initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
    )


def _two_backend_measurements(timestamps, positions):
    return {
        "rgb_vo": _measurement_trajectory("rgb_vo", timestamps, positions),
        "event_vo": _measurement_trajectory("event_vo", timestamps, positions),
    }


class TestWeightedEkfFusion:
    def test_accepts_consistent_updates_and_tracks_position(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        meas_pos = np.zeros((len(meas_t), 3))
        trajectory, records = _run_fusion(imu, _two_backend_measurements(meas_t, meas_pos))

        assert trajectory.method == "ensemble"
        assert len(trajectory.timestamps) == len(imu)
        accepted = [r for r in records if r.accepted]
        assert len(accepted) == 2 * len(meas_t)
        np.testing.assert_allclose(trajectory.positions[-1], np.zeros(3), atol=1e-3)
        assert str(trajectory.health[-1]) == "OK"

    def test_rejects_artificial_outlier_with_mahalanobis_reason(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        meas_pos = np.zeros((len(meas_t), 3))
        backends = _two_backend_measurements(meas_t, meas_pos)
        # One backend jumps 100 m at t=0.5 (an impossible teleport).
        outlier = np.zeros((len(meas_t), 3))
        outlier[4] = [100.0, 0.0, 0.0]
        backends["rgb_vo"] = _measurement_trajectory("rgb_vo", meas_t, outlier)

        _, records = _run_fusion(imu, backends)

        rejected = [r for r in records if not r.accepted and r.method == "rgb_vo"]
        assert len(rejected) == 1
        assert rejected[0].timestamp == pytest.approx(0.5)
        # The 100 m jump violates motion sanity before the chi-square check.
        assert rejected[0].reason == "motion_sanity_gate"

    def test_rejects_statistical_outlier_with_mahalanobis(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        meas_pos = np.zeros((len(meas_t), 3))
        backends = _two_backend_measurements(meas_t, meas_pos)
        # A 3 m jump within one 0.1 s gap is < 60 m/s but far outside the filter covariance.
        outlier = np.zeros((len(meas_t), 3))
        outlier[4] = [3.0, 0.0, 0.0]
        backends["rgb_vo"] = _measurement_trajectory("rgb_vo", meas_t, outlier)

        config = EkfFusionConfig(max_speed_mps=1000.0)
        _, records = _run_fusion(imu, backends, config)

        rejected = [r for r in records if not r.accepted and r.method == "rgb_vo"]
        assert len(rejected) == 1
        assert rejected[0].reason == "mahalanobis_gate"
        assert rejected[0].mahalanobis_d2 > config.chi2_threshold

    def test_rejects_lost_health_and_low_confidence(self):
        imu = _static_imu()
        meas_t = np.array([0.3, 0.6])
        meas_pos = np.zeros((2, 3))
        backends = {
            "rgb_vo": _measurement_trajectory("rgb_vo", meas_t, meas_pos, health="LOST"),
            "event_vo": _measurement_trajectory("event_vo", meas_t, meas_pos, confidence=0.05),
        }

        _, records = _run_fusion(imu, backends)

        reasons = {(r.method, r.reason) for r in records}
        assert ("rgb_vo", "health_gate") in reasons
        assert ("event_vo", "confidence_gate") in reasons
        assert all(not r.accepted for r in records)

    def test_trust_decays_to_lost_without_updates(self):
        imu = _static_imu(count=701, dt=0.01)  # 7 s
        meas_t = np.array([0.1, 0.2])
        meas_pos = np.zeros((2, 3))
        trajectory, _ = _run_fusion(imu, _two_backend_measurements(meas_t, meas_pos))

        # Right after the last update the state is OK; 5 s later it must be LOST.
        assert str(trajectory.health[21]) == "OK"
        assert str(trajectory.health[-1]) == "LOST"
        assert trajectory.confidence[-1] < 0.01

    def test_weight_columns_are_normalized_per_step(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        meas_pos = np.zeros((len(meas_t), 3))
        trajectory, _ = _run_fusion(imu, _two_backend_measurements(meas_t, meas_pos))

        w_rgb = trajectory.extra_columns["w_rgb"]
        w_event = trajectory.extra_columns["w_event"]
        update_steps = w_rgb + w_event
        assert np.count_nonzero(update_steps) == len(meas_t)
        np.testing.assert_allclose(update_steps[update_steps > 0], 1.0)
        # Identical confidence means equal split.
        np.testing.assert_allclose(w_rgb[w_rgb > 0], 0.5)

    def test_requires_imu(self):
        meas_t = np.array([0.1])
        backends = _two_backend_measurements(meas_t, np.zeros((1, 3)))
        with pytest.raises(ValueError, match="IMU"):
            _run_fusion(np.empty(0, dtype=IMU_DTYPE), backends)


class TestUpdateLogCsv:
    def test_writes_all_and_rejected_only(self, tmp_path):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        backends = _two_backend_measurements(meas_t, np.zeros((len(meas_t), 3)))
        backends["rgb_vo"] = _measurement_trajectory("rgb_vo", meas_t, np.zeros((len(meas_t), 3)), health="LOST")
        _, records = _run_fusion(imu, backends)

        all_path = tmp_path / "ensemble_updates.csv"
        rejected_path = tmp_path / "rejected_updates.csv"
        write_update_log_csv(records, all_path)
        write_update_log_csv(records, rejected_path, only_rejected=True)

        with open(all_path, newline="") as f:
            all_rows = list(csv.DictReader(f))
        with open(rejected_path, newline="") as f:
            rejected_rows = list(csv.DictReader(f))

        assert len(all_rows) == 2 * len(meas_t)
        assert len(rejected_rows) == len(meas_t)
        assert all(row["accepted"] == "false" for row in rejected_rows)
        assert all(row["reason"] == "health_gate" for row in rejected_rows)
        accepted_rows = [row for row in all_rows if row["accepted"] == "true"]
        assert all(row["method"] == "event_vo" for row in accepted_rows)


class TestWinnerTakesHealthy:
    def _backends(self):
        t = np.linspace(0.0, 1.0, 11)
        healthy_pos = np.column_stack([t, np.zeros_like(t), np.zeros_like(t)])
        sick_pos = healthy_pos + 5.0
        # event_imu has the higher static weight (0.50) vs rgb_vo (0.25).
        healthy = _measurement_trajectory("event_imu", t, healthy_pos, confidence=0.9)
        sick = _measurement_trajectory("rgb_vo", t, sick_pos, confidence=0.9)
        return t, healthy_pos, sick_pos, {"event_imu": healthy, "rgb_vo": sick}

    def test_follows_healthiest_backend(self):
        _t, healthy_pos, _, backends = self._backends()
        trajectory = run_winner_takes_healthy(backends)

        assert trajectory.method == "ensemble"
        np.testing.assert_allclose(trajectory.positions, healthy_pos, atol=1e-9)
        np.testing.assert_allclose(trajectory.extra_columns["w_event_imu"], 1.0)
        np.testing.assert_allclose(trajectory.extra_columns["w_rgb"], 0.0)

    def test_switches_when_winner_collapses(self):
        t, healthy_pos, sick_pos, backends = self._backends()
        # event_imu confidence collapses halfway through.
        collapsing_conf = np.where(t < 0.5, 0.9, 0.01)
        backends["event_imu"].confidence[:] = collapsing_conf

        trajectory = run_winner_takes_healthy(backends, config=WinnerTakesHealthyConfig(switch_margin=0.05))

        np.testing.assert_allclose(trajectory.positions[0], healthy_pos[0], atol=1e-9)
        np.testing.assert_allclose(trajectory.positions[-1], sick_pos[-1], atol=1e-9)
        assert trajectory.extra_columns["w_event_imu"][0] == 1.0
        assert trajectory.extra_columns["w_rgb"][-1] == 1.0

    def test_hysteresis_prevents_marginal_switch(self):
        t = np.linspace(0.0, 1.0, 5)
        pos_a = np.zeros((5, 3))
        pos_b = np.ones((5, 3))
        # Same static weight class: use two methods with close scores.
        a = _measurement_trajectory("event_imu", t, pos_a, confidence=0.60)
        b = _measurement_trajectory("image_imu", t, pos_b, confidence=0.61)

        trajectory = run_winner_takes_healthy(
            {"event_imu": a, "image_imu": b}, config=WinnerTakesHealthyConfig(switch_margin=0.10)
        )

        # image_imu is marginally better but within the margin, so the initial
        # argmax winner (image_imu at k=0) never flips; verify stability.
        winner_columns = trajectory.extra_columns["w_image_imu"]
        assert np.all(winner_columns == winner_columns[0])


class TestSampleBackendHealth:
    def test_resamples_health_onto_grid(self):
        t = np.array([0.0, 1.0])
        backends = {
            "rgb_vo": _measurement_trajectory("rgb_vo", t, np.zeros((2, 3)), health="DEGRADED"),
        }
        health = sample_backend_health(backends, np.array([0.0, 0.5, 1.0]))
        assert list(health["rgb_vo"]) == ["DEGRADED", "DEGRADED", "DEGRADED"]
