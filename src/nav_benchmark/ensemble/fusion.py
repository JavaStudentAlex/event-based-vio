"""Ensemble fusion runners: weighted error-state EKF and winner-takes-healthy.

Both consume standardized backend trajectories. The EKF mode propagates raw
IMU samples and applies gated absolute-position updates from backends; every
accepted and rejected update is recorded with an explicit reason.
"""

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from nav_benchmark.baselines.common import interpolate_trajectory
from nav_benchmark.ensemble.confidence_weighted import (
    ENSEMBLE_WEIGHT_COLUMNS,
    EnsembleConfig,
    _raw_weight_columns,
    _sample_trajectories,
    _target_timestamps,
    _validate_ensemble_inputs,
)
from nav_benchmark.ensemble.ekf import EkfConfig, ErrorStateEkf
from nav_benchmark.ensemble.gating import (
    GateDecision,
    confidence_gate,
    confidence_to_position_sigma,
    health_confidence_multiplier,
    health_gate,
    mahalanobis_distance_squared,
    motion_sanity_gate,
    timestamp_gate,
)
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

REASON_MAHALANOBIS = "mahalanobis_gate"

UPDATE_LOG_COLUMNS = (
    "timestamp",
    "method",
    "accepted",
    "reason",
    "innovation_norm_m",
    "mahalanobis_d2",
    "sigma_position_m",
    "confidence",
    "health",
)


@dataclass(frozen=True)
class UpdateRecord:
    """One backend measurement offered to the fusion filter."""

    timestamp: float
    method: str
    accepted: bool
    reason: str | None
    innovation_norm_m: float | None
    mahalanobis_d2: float | None
    sigma_position_m: float | None
    confidence: float
    health: str


@dataclass
class EkfFusionConfig:
    """Gating, trust, and filter configuration for weighted EKF fusion."""

    ekf: EkfConfig = field(default_factory=EkfConfig)
    sigma_position_min: float = 0.05
    sigma_position_range: float = 5.0
    chi2_threshold: float = 16.27  # chi-square 3 dof at 99.9%
    max_measurement_age_sec: float = 0.25
    max_speed_mps: float = 60.0
    min_backend_confidence: float = 0.15
    degraded_confidence_multiplier: float = 0.35
    trust_decay_tau_sec: float = 1.0
    ok_update_age_sec: float = 0.5
    lost_update_age_sec: float = 5.0


@dataclass(frozen=True)
class _Measurement:
    timestamp: float
    method: str
    position: np.ndarray
    confidence: float
    health: str


def _trajectory_measurements(method: str, trajectory: Trajectory) -> list[_Measurement]:
    count = len(trajectory.timestamps)
    confidence = trajectory.confidence if trajectory.confidence is not None else np.ones(count)
    health = trajectory.health if trajectory.health is not None else np.array([PoseHealth.OK.value] * count)
    return [
        _Measurement(
            timestamp=float(trajectory.timestamps[i]),
            method=method,
            position=trajectory.positions[i].astype(np.float64),
            confidence=float(confidence[i]),
            health=str(health[i]),
        )
        for i in range(count)
    ]


def _sorted_measurements(backend_trajectories: dict[str, Trajectory]) -> list[_Measurement]:
    measurements: list[_Measurement] = []
    for method, trajectory in backend_trajectories.items():
        measurements.extend(_trajectory_measurements(method, trajectory))
    measurements.sort(key=lambda m: m.timestamp)
    return measurements


@dataclass
class _GateOutcome:
    decision: GateDecision
    innovation_norm_m: float | None = None
    mahalanobis_d2: float | None = None
    sigma_position_m: float | None = None


def _pre_update_gates(measurement: _Measurement, state_time: float, config: EkfFusionConfig) -> GateDecision:
    decision = health_gate(measurement.health)
    if not decision.accepted:
        return decision
    decision = confidence_gate(measurement.confidence, config.min_backend_confidence)
    if not decision.accepted:
        return decision
    return timestamp_gate(measurement.timestamp, state_time, config.max_measurement_age_sec)


def _measurement_sigma(measurement: _Measurement, config: EkfFusionConfig) -> float:
    effective = measurement.confidence * health_confidence_multiplier(
        measurement.health, config.degraded_confidence_multiplier
    )
    return confidence_to_position_sigma(effective, config.sigma_position_min, config.sigma_position_range)


def _gate_measurement(
    ekf: ErrorStateEkf,
    measurement: _Measurement,
    state_time: float,
    last_accepted_time: float,
    config: EkfFusionConfig,
    *,
    sigma: float | None = None,
) -> _GateOutcome:
    decision = _pre_update_gates(measurement, state_time, config)
    if not decision.accepted:
        return _GateOutcome(decision=decision)

    if sigma is None:
        sigma = _measurement_sigma(measurement, config)
    innovation, S = ekf.innovation(measurement.position, sigma)
    innovation_norm = float(np.linalg.norm(innovation))

    decision = motion_sanity_gate(innovation_norm, state_time - last_accepted_time, config.max_speed_mps)
    if not decision.accepted:
        return _GateOutcome(decision=decision, innovation_norm_m=innovation_norm, sigma_position_m=sigma)

    d2 = mahalanobis_distance_squared(innovation, S)
    if d2 > config.chi2_threshold:
        decision = GateDecision(accepted=False, reason=REASON_MAHALANOBIS)
    return _GateOutcome(decision=decision, innovation_norm_m=innovation_norm, mahalanobis_d2=d2, sigma_position_m=sigma)


def _record_from_outcome(measurement: _Measurement, outcome: _GateOutcome) -> UpdateRecord:
    return UpdateRecord(
        timestamp=measurement.timestamp,
        method=measurement.method,
        accepted=outcome.decision.accepted,
        reason=outcome.decision.reason,
        innovation_norm_m=outcome.innovation_norm_m,
        mahalanobis_d2=outcome.mahalanobis_d2,
        sigma_position_m=outcome.sigma_position_m,
        confidence=measurement.confidence,
        health=measurement.health,
    )


def _trust_from_update_age(age_sec: float, config: EkfFusionConfig) -> tuple[float, str]:
    confidence = float(np.exp(-age_sec / config.trust_decay_tau_sec))
    if age_sec <= config.ok_update_age_sec:
        return confidence, PoseHealth.OK.value
    if age_sec <= config.lost_update_age_sec:
        return confidence, PoseHealth.DEGRADED.value
    return confidence, PoseHealth.LOST.value


def _normalized_step_weights(step_weights: dict[str, np.ndarray], count: int) -> dict[str, np.ndarray]:
    total = np.zeros(count, dtype=np.float64)
    for values in step_weights.values():
        total += values
    normalized: dict[str, np.ndarray] = {}
    for method, column in ENSEMBLE_WEIGHT_COLUMNS.items():
        raw = step_weights.get(method, np.zeros(count, dtype=np.float64))
        normalized[column] = np.divide(raw, total, out=np.zeros_like(raw), where=total > 0.0)
    return normalized


@dataclass
class _FusionState:
    """Mutable accumulators for one weighted-EKF fusion pass."""

    positions: np.ndarray
    velocities: np.ndarray
    orientations: np.ndarray
    confidence: np.ndarray
    health: np.ndarray
    step_weights: dict[str, np.ndarray]
    records: list[UpdateRecord]
    last_accepted_time: float


def _init_fusion_state(ekf: ErrorStateEkf, count: int, methods: list[str], start_time: float) -> _FusionState:
    state = _FusionState(
        positions=np.zeros((count, 3)),
        velocities=np.zeros((count, 3)),
        orientations=np.zeros((count, 4)),
        confidence=np.zeros(count),
        health=np.empty(count, dtype=object),
        step_weights={method: np.zeros(count, dtype=np.float64) for method in methods},
        records=[],
        last_accepted_time=start_time,
    )
    state.positions[0] = ekf.position
    state.velocities[0] = ekf.velocity
    state.orientations[0] = ekf.orientation_xyzw
    state.confidence[0] = 1.0
    state.health[0] = PoseHealth.OK.value
    return state


def _apply_measurement(
    ekf: ErrorStateEkf,
    measurement: _Measurement,
    state_time: float,
    step_index: int,
    state: _FusionState,
    config: EkfFusionConfig,
) -> None:
    outcome = _gate_measurement(ekf, measurement, state_time, state.last_accepted_time, config)
    state.records.append(_record_from_outcome(measurement, outcome))
    if not outcome.decision.accepted:
        return
    sigma = outcome.sigma_position_m if outcome.sigma_position_m is not None else config.sigma_position_min
    ekf.update_position(measurement.position, sigma)
    state.last_accepted_time = measurement.timestamp
    state.step_weights[measurement.method][step_index] += 1.0 / sigma**2


def _store_step(
    ekf: ErrorStateEkf, state: _FusionState, index: int, state_time: float, config: EkfFusionConfig
) -> None:
    state.positions[index] = ekf.position
    state.velocities[index] = ekf.velocity
    state.orientations[index] = ekf.orientation_xyzw
    confidence, health = _trust_from_update_age(state_time - state.last_accepted_time, config)
    state.confidence[index] = confidence
    state.health[index] = health


def _propagate_imu_step(ekf: ErrorStateEkf, imu: np.ndarray, index: int) -> None:
    dt = max(float(imu["t"][index + 1] - imu["t"][index]), 1e-6)
    accel = np.array([imu["ax"][index], imu["ay"][index], imu["az"][index]], dtype=np.float64)
    gyro = np.array([imu["gx"][index], imu["gy"][index], imu["gz"][index]], dtype=np.float64)
    ekf.propagate(accel, gyro, dt)


def _apply_measurements_until(
    ekf: ErrorStateEkf,
    measurements: list[_Measurement],
    start_index: int,
    state_time: float,
    step_index: int,
    state: "_FusionState",
    config: EkfFusionConfig,
) -> int:
    j = start_index
    while j < len(measurements) and measurements[j].timestamp <= state_time:
        _apply_measurement(ekf, measurements[j], state_time, step_index, state, config)
        j += 1
    return j


def run_weighted_ekf_fusion(
    imu: np.ndarray,
    backend_trajectories: dict[str, Trajectory],
    *,
    config: EkfFusionConfig | None = None,
    initial_position: np.ndarray,
    initial_velocity: np.ndarray,
    initial_orientation_xyzw: np.ndarray,
) -> tuple[Trajectory, list[UpdateRecord]]:
    """Fuse backend pose streams over IMU propagation into one gated EKF trajectory."""
    if imu is None or len(imu) == 0:
        raise ValueError("Weighted EKF fusion requires IMU samples for propagation")
    _validate_ensemble_inputs(backend_trajectories)
    cfg = config if config is not None else EkfFusionConfig()

    start_wall = time.perf_counter()
    ekf = ErrorStateEkf(
        cfg.ekf,
        initial_position=initial_position,
        initial_velocity=initial_velocity,
        initial_orientation_xyzw=initial_orientation_xyzw,
    )

    t = np.asarray(imu["t"], dtype=np.float64)
    count = len(t)
    measurements = _sorted_measurements(backend_trajectories)
    state = _init_fusion_state(ekf, count, sorted(backend_trajectories), float(t[0]))

    next_measurement = 0
    for i in range(count - 1):
        _propagate_imu_step(ekf, imu, i)
        state_time = float(t[i + 1])
        next_measurement = _apply_measurements_until(ekf, measurements, next_measurement, state_time, i + 1, state, cfg)
        _store_step(ekf, state, i + 1, state_time, cfg)

    elapsed_ms = (time.perf_counter() - start_wall) * 1000.0
    trajectory = Trajectory(
        timestamps=t,
        method="ensemble",
        positions=state.positions,
        orientations=state.orientations,
        velocities=state.velocities,
        confidence=state.confidence,
        health=state.health,
        latency_ms=np.full(count, elapsed_ms / count),
        extra_columns=_normalized_step_weights(state.step_weights, count),
    )
    return trajectory, state.records


def _update_log_row(record: UpdateRecord) -> list[str]:
    def _opt(value: float | None) -> str:
        return "" if value is None else f"{value:.9f}"

    return [
        f"{record.timestamp:.9f}",
        record.method,
        str(record.accepted).lower(),
        record.reason or "",
        _opt(record.innovation_norm_m),
        _opt(record.mahalanobis_d2),
        _opt(record.sigma_position_m),
        f"{record.confidence:.9f}",
        record.health,
    ]


def write_update_log_csv(records: list[UpdateRecord], path: str | Path, *, only_rejected: bool = False) -> None:
    """Write accepted/rejected fusion updates (with reasons) to a CSV log."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    selected = [r for r in records if not (only_rejected and r.accepted)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(UPDATE_LOG_COLUMNS)
        writer.writerows(_update_log_row(record) for record in selected)


@dataclass
class WinnerTakesHealthyConfig:
    """Configuration for the winner-takes-healthy fallback fusion mode."""

    base: EnsembleConfig = field(default_factory=EnsembleConfig)
    switch_margin: float = 0.10


def _winner_indices(scores: dict[str, np.ndarray], methods: list[str], margin: float) -> np.ndarray:
    count = len(next(iter(scores.values())))
    winners = np.zeros(count, dtype=np.int64)
    stacked = np.stack([scores[m] for m in methods], axis=0)
    current = int(np.argmax(stacked[:, 0]))
    for k in range(count):
        challenger = int(np.argmax(stacked[:, k]))
        # Switch only when the challenger clearly beats the incumbent (hysteresis).
        if challenger != current and stacked[challenger, k] > stacked[current, k] + margin:
            current = challenger
        winners[k] = current
    return winners


def run_winner_takes_healthy(
    backend_trajectories: dict[str, Trajectory],
    *,
    config: WinnerTakesHealthyConfig | None = None,
) -> Trajectory:
    """Follow the single healthiest backend at each step, switching with hysteresis."""
    _validate_ensemble_inputs(backend_trajectories)
    cfg = config if config is not None else WinnerTakesHealthyConfig()

    timestamps = np.asarray(_target_timestamps(backend_trajectories, cfg.base), dtype=np.float64)
    sampled = _sample_trajectories(backend_trajectories, timestamps)
    scores = _raw_weight_columns(sampled, cfg.base)
    methods = sorted(backend_trajectories)
    winners = _winner_indices(scores, methods, cfg.switch_margin)

    count = len(timestamps)
    positions = np.zeros((count, 3))
    velocities = np.zeros((count, 3))
    orientations = np.zeros((count, 4))
    confidence = np.zeros(count)
    health = np.empty(count, dtype=object)
    weights = {column: np.zeros(count, dtype=np.float64) for column in ENSEMBLE_WEIGHT_COLUMNS.values()}

    for k in range(count):
        winner = methods[winners[k]]
        data = sampled[winner]
        positions[k] = data.positions[k]
        velocities[k] = data.velocities[k]
        orientations[k] = data.orientations[k]
        confidence[k] = data.confidence[k]
        health[k] = data.health[k]
        weights[ENSEMBLE_WEIGHT_COLUMNS[winner]][k] = 1.0

    return Trajectory(
        timestamps=timestamps,
        method="ensemble",
        positions=positions,
        orientations=orientations,
        velocities=velocities,
        confidence=np.clip(confidence, 0.0, 1.0),
        health=health,
        latency_ms=np.zeros(count),
        extra_columns=weights,
    )


def sample_backend_health(backend_trajectories: dict[str, Trajectory], timestamps: np.ndarray) -> dict[str, np.ndarray]:
    """Backend health labels resampled onto a common time grid (for status timelines)."""
    return {
        method: interpolate_trajectory(trajectory, timestamps).health
        for method, trajectory in backend_trajectories.items()
    }
