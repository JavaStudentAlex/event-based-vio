"""Trust-gated fusion core: parity with the weighted EKF and policy-gate semantics."""

from itertools import pairwise

import numpy as np
import pytest

from nav_benchmark.datasets.mvsec import IMU_DTYPE
from nav_benchmark.ensemble.fusion import run_weighted_ekf_fusion
from nav_benchmark.ensemble.rl_gated import (
    REASON_POLICY,
    GatedEkfFusionCore,
    RlGatedFusionConfig,
    _control_boundaries,
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


def _two_backend_measurements(timestamps: np.ndarray, positions: np.ndarray) -> dict[str, Trajectory]:
    return {
        "rgb_vo": _measurement_trajectory("rgb_vo", timestamps, positions),
        "event_vo": _measurement_trajectory("event_vo", timestamps, positions),
    }


def _run_core(imu, backends, trusts_per_step, config=None):
    core = GatedEkfFusionCore(
        imu,
        backends,
        config=config,
        initial_position=np.zeros(3),
        initial_velocity=np.zeros(3),
        initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
    )
    summaries = [core.step(trusts_per_step(k, core.methods)) for k in range(core.num_steps)]
    trajectory, records = core.result()
    return core, summaries, trajectory, records


def _full_trust(_k, methods):
    return dict.fromkeys(methods, 1.0)


class TestControlBoundaries:
    def test_partitions_all_propagation_steps(self):
        t = np.arange(101) * 0.01
        bounds = _control_boundaries(t, 0.1)
        covered = [i for first, last in bounds for i in range(first, last + 1)]
        assert covered == list(range(100))
        assert all(first <= last for first, last in bounds)

    def test_irregular_timestamps_never_produce_empty_windows(self):
        t = np.array([0.0, 0.001, 0.002, 0.5, 0.501, 1.2])
        bounds = _control_boundaries(t, 0.1)
        covered = [i for first, last in bounds for i in range(first, last + 1)]
        assert covered == list(range(len(t) - 1))

    def test_rejects_non_positive_period(self):
        with pytest.raises(ValueError, match="control_period_sec"):
            _control_boundaries(np.array([0.0, 1.0]), 0.0)


class TestWeightedEkfParity:
    def test_full_trust_reproduces_weighted_ekf_exactly(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        meas_pos = np.tile(np.array([[0.02, -0.01, 0.005]]), (len(meas_t), 1))
        backends = _two_backend_measurements(meas_t, meas_pos)

        reference, reference_records = run_weighted_ekf_fusion(
            imu,
            backends,
            initial_position=np.zeros(3),
            initial_velocity=np.zeros(3),
            initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
        )
        _, _, trajectory, records = _run_core(imu, backends, _full_trust)

        np.testing.assert_allclose(trajectory.positions, reference.positions, atol=0.0)
        np.testing.assert_allclose(trajectory.velocities, reference.velocities, atol=0.0)
        np.testing.assert_allclose(trajectory.confidence, reference.confidence, atol=0.0)
        assert list(trajectory.health) == list(reference.health)
        for column in reference.extra_columns:
            np.testing.assert_allclose(trajectory.extra_columns[column], reference.extra_columns[column], atol=0.0)
        assert [(r.method, r.timestamp, r.accepted, r.reason) for r in records] == [
            (r.method, r.timestamp, r.accepted, r.reason) for r in reference_records
        ]

    def test_full_trust_parity_survives_outliers_and_bad_health(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        good = np.zeros((len(meas_t), 3))
        outlier = good.copy()
        outlier[4] = [3.0, 0.0, 0.0]
        backends = {
            "rgb_vo": _measurement_trajectory("rgb_vo", meas_t, outlier),
            "event_vo": _measurement_trajectory("event_vo", meas_t, good, health="DEGRADED"),
        }

        reference, reference_records = run_weighted_ekf_fusion(
            imu,
            backends,
            initial_position=np.zeros(3),
            initial_velocity=np.zeros(3),
            initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
        )
        _, _, trajectory, records = _run_core(imu, backends, _full_trust)

        np.testing.assert_allclose(trajectory.positions, reference.positions, atol=0.0)
        assert [(r.accepted, r.reason) for r in records] == [(r.accepted, r.reason) for r in reference_records]


class TestPolicyGate:
    def test_zero_trust_rejects_everything_with_policy_reason(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        backends = _two_backend_measurements(meas_t, np.zeros((len(meas_t), 3)))

        _, _, _, records = _run_core(imu, backends, lambda _k, methods: dict.fromkeys(methods, 0.0))

        assert len(records) == 2 * len(meas_t)
        assert all(not r.accepted for r in records)
        assert {r.reason for r in records} == {REASON_POLICY}

    def test_low_trust_downweights_a_biased_backend(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        good = np.zeros((len(meas_t), 3))
        biased = good + np.array([1.5, 0.0, 0.0])
        backends = {
            "rgb_vo": _measurement_trajectory("rgb_vo", meas_t, biased),
            "event_vo": _measurement_trajectory("event_vo", meas_t, good),
        }
        config = RlGatedFusionConfig()
        config.base.chi2_threshold = 1e9  # isolate the trust effect from the chi-square gate

        def naive(_k, methods):
            return dict.fromkeys(methods, 1.0)

        def informed(_k, _methods):
            return {"rgb_vo": 0.06, "event_vo": 1.0}

        _, _, naive_traj, _ = _run_core(imu, backends, naive, config=config)
        _, _, informed_traj, _ = _run_core(imu, backends, informed, config=config)

        naive_error = float(np.linalg.norm(naive_traj.positions[-1]))
        informed_error = float(np.linalg.norm(informed_traj.positions[-1]))
        assert informed_error < naive_error

    def test_hard_gates_still_apply_under_full_trust(self):
        imu = _static_imu()
        meas_t = np.arange(0.1, 1.01, 0.1)
        outlier = np.zeros((len(meas_t), 3))
        outlier[4] = [100.0, 0.0, 0.0]
        backends = {
            "rgb_vo": _measurement_trajectory("rgb_vo", meas_t, outlier),
            "event_vo": _measurement_trajectory("event_vo", meas_t, np.zeros((len(meas_t), 3))),
        }

        _, _, _, records = _run_core(imu, backends, _full_trust)

        rejected = [r for r in records if not r.accepted and r.method == "rgb_vo"]
        assert len(rejected) == 1
        assert rejected[0].reason == "motion_sanity_gate"


class TestSummaries:
    def test_summaries_expose_offer_counts_and_staleness(self):
        imu = _static_imu()
        meas_t = np.array([0.15, 0.25])
        backends = _two_backend_measurements(meas_t, np.zeros((2, 3)))

        _, summaries, _, _ = _run_core(imu, backends, _full_trust)

        offered = [sum(s.stats[m].offered for m in s.stats) for s in summaries]
        assert sum(offered) == 4
        # After measurements stop, per-method staleness must grow monotonically.
        tail = [s.last_accept_age_sec["rgb_vo"] for s in summaries[3:]]
        assert all(b > a for a, b in pairwise(tail))
        # Innovation statistics are recorded for offered measurements.
        assert any(s.stats["rgb_vo"].innovation_count > 0 for s in summaries)

    def test_trust_vector_shape_is_validated(self):
        imu = _static_imu(count=11)
        backends = _two_backend_measurements(np.array([0.05]), np.zeros((1, 3)))
        core = GatedEkfFusionCore(
            imu,
            backends,
            initial_position=np.zeros(3),
            initial_velocity=np.zeros(3),
            initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
        )
        with pytest.raises(ValueError, match="trust values"):
            core.step(np.array([1.0, 1.0, 1.0]))
        with pytest.raises(ValueError, match="Missing trust"):
            core.step({"rgb_vo": 1.0})

    def test_result_requires_all_steps_consumed(self):
        imu = _static_imu(count=21)
        backends = _two_backend_measurements(np.array([0.05]), np.zeros((1, 3)))
        core = GatedEkfFusionCore(
            imu,
            backends,
            initial_position=np.zeros(3),
            initial_velocity=np.zeros(3),
            initial_orientation_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
        )
        with pytest.raises(RuntimeError, match="control steps"):
            core.result()
