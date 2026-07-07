"""Trust-gated weighted EKF fusion core for the learned (RL) ensemble.

The core exposes the weighted EKF fusion loop at control-step granularity so a
learned policy can modulate per-backend trust while the estimator itself stays
the deterministic error-state EKF. Training (``nav_benchmark.rl``) and
benchmark inference share this single stepping implementation, which prevents
train/inference skew.

Trust semantics: a per-backend value in ``[0, 1]`` multiplies the backend's
reported confidence before the confidence-to-sigma mapping. ``trust == 1``
reproduces :func:`nav_benchmark.ensemble.fusion.run_weighted_ekf_fusion`
exactly. Trust below ``min_trust_to_apply`` excludes the measurement with an
explicit ``policy_gate`` reason. Hard safety gates (health, raw confidence,
timestamp, motion sanity, chi-square) always stay active so a policy cannot
force physically inconsistent updates into the filter.
"""

from dataclasses import dataclass, field

import numpy as np

from nav_benchmark.ensemble.ekf import ErrorStateEkf
from nav_benchmark.ensemble.fusion import (
    EkfFusionConfig,
    UpdateRecord,
    _FusionState,
    _gate_measurement,
    _GateOutcome,
    _init_fusion_state,
    _Measurement,
    _normalized_step_weights,
    _propagate_imu_step,
    _record_from_outcome,
    _sorted_measurements,
    _store_step,
    _validate_ensemble_inputs,
)
from nav_benchmark.ensemble.gating import (
    GateDecision,
    confidence_to_position_sigma,
    health_confidence_multiplier,
    mahalanobis_distance_squared,
)
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

REASON_POLICY = "policy_gate"


@dataclass
class RlGatedFusionConfig:
    """Configuration for trust-gated EKF fusion driven by a learned policy."""

    base: EkfFusionConfig = field(default_factory=EkfFusionConfig)
    control_period_sec: float = 0.10
    min_trust_to_apply: float = 0.05


@dataclass
class MethodWindowStats:
    """Per-backend aggregates over one control window (policy observation inputs)."""

    offered: int = 0
    accepted: int = 0
    confidence_sum: float = 0.0
    degraded: int = 0
    failed: int = 0
    innovation_sum_m: float = 0.0
    innovation_count: int = 0
    d2_sum: float = 0.0
    d2_count: int = 0

    @property
    def mean_confidence(self) -> float:
        return self.confidence_sum / self.offered if self.offered else 0.0

    @property
    def frac_degraded(self) -> float:
        return self.degraded / self.offered if self.offered else 0.0

    @property
    def frac_failed(self) -> float:
        return self.failed / self.offered if self.offered else 0.0

    @property
    def mean_innovation_m(self) -> float:
        return self.innovation_sum_m / self.innovation_count if self.innovation_count else 0.0

    @property
    def mean_d2(self) -> float:
        return self.d2_sum / self.d2_count if self.d2_count else 0.0

    @property
    def accept_ratio(self) -> float:
        return self.accepted / self.offered if self.offered else 0.0


@dataclass(frozen=True)
class ControlStepSummary:
    """Filter and measurement statistics after one control step."""

    index: int
    start_time: float
    end_time: float
    stats: dict[str, MethodWindowStats]
    last_accept_age_sec: dict[str, float]
    ekf_position_sigma_m: float
    ekf_speed_mps: float
    applied_trust: dict[str, float]


def _control_boundaries(t: np.ndarray, period_sec: float) -> list[tuple[int, int]]:
    """Split propagation steps ``i -> i+1`` into contiguous control windows.

    Returns inclusive ``(first_step, last_step)`` index pairs covering
    ``0 .. len(t) - 2``. Every window contains at least one propagation step, so
    degenerate IMU timing cannot produce empty control steps.
    """
    _validate_control_period(period_sec)
    last = len(t) - 2
    if last < 0:
        return []
    boundaries: list[tuple[int, int]] = []
    start = 0
    while start <= last:
        end = _control_window_end(t, start, last, period_sec)
        boundaries.append((start, end))
        start = end + 1
    return boundaries


def _validate_control_period(period_sec: float) -> None:
    if period_sec <= 0.0:
        raise ValueError("control_period_sec must be positive")


def _control_window_end(t: np.ndarray, start: int, last: int, period_sec: float) -> int:
    deadline = float(t[start]) + period_sec
    end = start
    while end < last and float(t[end + 1]) < deadline:
        end += 1
    return end


def _health_counts_key(health: str) -> str:
    if health == PoseHealth.DEGRADED.value:
        return "degraded"
    if health in (PoseHealth.LOST.value, PoseHealth.INVALID.value):
        return "failed"
    return "ok"


class GatedEkfFusionCore:
    """Step-driven weighted EKF fusion with per-backend trust inputs.

    The constructor mirrors :func:`run_weighted_ekf_fusion`; ``step`` consumes
    one control window with a trust vector and returns the observation
    statistics for the next policy decision. ``result`` assembles the standard
    ensemble trajectory once every control step has been consumed.
    """

    def __init__(
        self,
        imu: np.ndarray,
        backend_trajectories: dict[str, Trajectory],
        *,
        config: RlGatedFusionConfig | None = None,
        initial_position: np.ndarray,
        initial_velocity: np.ndarray,
        initial_orientation_xyzw: np.ndarray,
    ) -> None:
        if imu is None or len(imu) == 0:
            raise ValueError("Trust-gated EKF fusion requires IMU samples for propagation")
        _validate_ensemble_inputs(backend_trajectories)
        self.config = config if config is not None else RlGatedFusionConfig()
        self.methods: list[str] = sorted(backend_trajectories)
        self._imu = imu
        self._t = np.asarray(imu["t"], dtype=np.float64)
        self._measurements: list[_Measurement] = _sorted_measurements(backend_trajectories)
        self._boundaries = _control_boundaries(self._t, self.config.control_period_sec)
        self._ekf = ErrorStateEkf(
            self.config.base.ekf,
            initial_position=initial_position,
            initial_velocity=initial_velocity,
            initial_orientation_xyzw=initial_orientation_xyzw,
        )
        self._state: _FusionState = _init_fusion_state(self._ekf, len(self._t), self.methods, float(self._t[0]))
        self._next_measurement = 0
        self._step_index = 0
        self._last_accept_time = dict.fromkeys(self.methods, float(self._t[0]))

    @property
    def num_steps(self) -> int:
        return len(self._boundaries)

    @property
    def step_index(self) -> int:
        return self._step_index

    def step_end_time(self, index: int) -> float:
        """State timestamp reached after control step ``index``."""
        return float(self._t[self._boundaries[index][1] + 1])

    def state_position(self) -> np.ndarray:
        return self._ekf.position.copy()

    def _trusted_sigma(self, measurement: _Measurement, trust: float) -> float:
        multiplier = health_confidence_multiplier(measurement.health, self.config.base.degraded_confidence_multiplier)
        effective = measurement.confidence * multiplier * float(np.clip(trust, 0.0, 1.0))
        return confidence_to_position_sigma(
            effective, self.config.base.sigma_position_min, self.config.base.sigma_position_range
        )

    def _tally_offer(self, stats: MethodWindowStats, measurement: _Measurement) -> None:
        stats.offered += 1
        stats.confidence_sum += measurement.confidence
        bucket = _health_counts_key(measurement.health)
        if bucket == "degraded":
            stats.degraded += 1
        elif bucket == "failed":
            stats.failed += 1

    def _tally_innovation(self, stats: MethodWindowStats, outcome: _GateOutcome, measurement: _Measurement) -> None:
        if outcome.innovation_norm_m is None:
            return
        stats.innovation_sum_m += outcome.innovation_norm_m
        stats.innovation_count += 1
        # Feature-facing d2 uses the trust-independent base sigma so the policy
        # sees comparable disagreement magnitudes regardless of its own action.
        base_sigma = self._trusted_sigma(measurement, 1.0)
        innovation, S = self._ekf.innovation(measurement.position, base_sigma)
        stats.d2_sum += mahalanobis_distance_squared(innovation, S)
        stats.d2_count += 1

    def _gate_with_trust(self, measurement: _Measurement, trust: float, state_time: float) -> _GateOutcome:
        sigma = self._trusted_sigma(measurement, trust)
        outcome = _gate_measurement(
            self._ekf, measurement, state_time, self._state.last_accepted_time, self.config.base, sigma=sigma
        )
        if outcome.decision.accepted and trust < self.config.min_trust_to_apply:
            return _GateOutcome(
                decision=GateDecision(accepted=False, reason=REASON_POLICY),
                innovation_norm_m=outcome.innovation_norm_m,
                mahalanobis_d2=outcome.mahalanobis_d2,
                sigma_position_m=outcome.sigma_position_m,
            )
        return outcome

    def _apply_measurement(
        self,
        measurement: _Measurement,
        trust: float,
        state_time: float,
        step_index: int,
        stats: dict[str, MethodWindowStats],
    ) -> None:
        method_stats = stats[measurement.method]
        self._tally_offer(method_stats, measurement)
        outcome = self._gate_with_trust(measurement, trust, state_time)
        self._tally_innovation(method_stats, outcome, measurement)
        self._state.records.append(_record_from_outcome(measurement, outcome))
        if not outcome.decision.accepted:
            return
        sigma = (
            outcome.sigma_position_m if outcome.sigma_position_m is not None else self.config.base.sigma_position_min
        )
        self._ekf.update_position(measurement.position, sigma)
        self._state.last_accepted_time = measurement.timestamp
        self._last_accept_time[measurement.method] = measurement.timestamp
        self._state.step_weights[measurement.method][step_index] += 1.0 / sigma**2
        method_stats.accepted += 1

    def _trust_map_from_dict(self, trusts: dict[str, float]) -> dict[str, float]:
        missing = [method for method in self.methods if method not in trusts]
        if missing:
            raise ValueError(f"Missing trust values for methods: {missing}")
        return {method: float(np.clip(trusts[method], 0.0, 1.0)) for method in self.methods}

    def _trust_map_from_array(self, trusts: np.ndarray) -> dict[str, float]:
        values = np.asarray(trusts, dtype=np.float64).reshape(-1)
        if values.size != len(self.methods):
            raise ValueError(f"Expected {len(self.methods)} trust values, got {values.size}")
        return {method: float(np.clip(values[index], 0.0, 1.0)) for index, method in enumerate(self.methods)}

    def _trust_map(self, trusts: dict[str, float] | np.ndarray) -> dict[str, float]:
        if isinstance(trusts, dict):
            return self._trust_map_from_dict(trusts)
        return self._trust_map_from_array(trusts)

    def _empty_window_stats(self) -> dict[str, MethodWindowStats]:
        return {method: MethodWindowStats() for method in self.methods}

    def _consume_measurements_until(
        self,
        state_time: float,
        state_index: int,
        trust_map: dict[str, float],
        stats: dict[str, MethodWindowStats],
    ) -> None:
        while self._next_measurement < len(self._measurements):
            measurement = self._measurements[self._next_measurement]
            if measurement.timestamp > state_time:
                break
            self._apply_measurement(measurement, trust_map[measurement.method], state_time, state_index, stats)
            self._next_measurement += 1

    def _run_control_window(
        self,
        first: int,
        last: int,
        trust_map: dict[str, float],
        stats: dict[str, MethodWindowStats],
    ) -> None:
        for i in range(first, last + 1):
            _propagate_imu_step(self._ekf, self._imu, i)
            state_time = float(self._t[i + 1])
            self._consume_measurements_until(state_time, i + 1, trust_map, stats)
            _store_step(self._ekf, self._state, i + 1, state_time, self.config.base)

    def _control_step_summary(
        self,
        start_time: float,
        end_time: float,
        stats: dict[str, MethodWindowStats],
        trust_map: dict[str, float],
    ) -> ControlStepSummary:
        return ControlStepSummary(
            index=self._step_index,
            start_time=start_time,
            end_time=end_time,
            stats=stats,
            last_accept_age_sec={method: end_time - self._last_accept_time[method] for method in self.methods},
            ekf_position_sigma_m=self._ekf.position_sigma(),
            ekf_speed_mps=float(np.linalg.norm(self._ekf.velocity)),
            applied_trust=trust_map,
        )

    def step(self, trusts: dict[str, float] | np.ndarray) -> ControlStepSummary:
        """Advance one control window applying ``trusts`` to every measurement in it."""
        if self._step_index >= self.num_steps:
            raise RuntimeError("All control steps have already been consumed")
        trust_map = self._trust_map(trusts)
        first, last = self._boundaries[self._step_index]
        start_time = float(self._t[first])
        stats = self._empty_window_stats()

        self._run_control_window(first, last, trust_map, stats)

        end_time = float(self._t[last + 1])
        summary = self._control_step_summary(start_time, end_time, stats, trust_map)
        self._step_index += 1
        return summary

    def result(self, *, elapsed_ms_total: float = 0.0) -> tuple[Trajectory, list[UpdateRecord]]:
        """Assemble the fused ensemble trajectory once all control steps ran."""
        if self._step_index != self.num_steps:
            raise RuntimeError(f"Fusion consumed {self._step_index} of {self.num_steps} control steps")
        count = len(self._t)
        trajectory = Trajectory(
            timestamps=self._t,
            method="ensemble",
            positions=self._state.positions,
            orientations=self._state.orientations,
            velocities=self._state.velocities,
            confidence=self._state.confidence,
            health=self._state.health,
            latency_ms=np.full(count, elapsed_ms_total / count),
            extra_columns=_normalized_step_weights(self._state.step_weights, count),
        )
        return trajectory, self._state.records
