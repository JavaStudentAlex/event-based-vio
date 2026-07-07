"""Deterministic backend degradations for RL fusion training episodes.

Real MVSEC backends fail rarely and always in the same places, which is not
enough signal to learn gating. Training therefore injects seeded, fully
reproducible degradations into backend measurement streams: honest failures
(dropout, noisy bursts, drifting bias with lowered confidence) and the
adversarial case of a backend that drifts while still reporting high
confidence. The policy has to detect the latter from innovation/agreement
features rather than from the reported confidence.
"""

from dataclasses import dataclass

import numpy as np

from nav_benchmark.trajectory.models import PoseHealth, Trajectory

KIND_DROPOUT = "dropout"
KIND_BIAS_RAMP = "bias_ramp"
KIND_NOISE_BURST = "noise_burst"
KIND_CONFIDENT_BIAS = "confident_bias"
PERTURBATION_KINDS = (KIND_DROPOUT, KIND_BIAS_RAMP, KIND_NOISE_BURST, KIND_CONFIDENT_BIAS)

_HONEST_BIAS_CONFIDENCE_SCALE = 0.6
_NOISE_CONFIDENCE_SCALE = 0.7


@dataclass(frozen=True)
class BackendPerturbation:
    """One seeded degradation of one backend inside ``[t_start, t_end]``."""

    method: str
    kind: str
    t_start: float
    t_end: float
    magnitude_m: float
    direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    seed: int = 0

    def __post_init__(self) -> None:
        if self.kind not in PERTURBATION_KINDS:
            raise ValueError(f"Unknown perturbation kind: {self.kind!r}")
        if self.t_end <= self.t_start:
            raise ValueError("Perturbation window must have positive duration")
        if self.magnitude_m < 0.0:
            raise ValueError("Perturbation magnitude must be non-negative")


def _copied_trajectory(trajectory: Trajectory) -> Trajectory:
    count = len(trajectory.timestamps)
    confidence = trajectory.confidence.copy() if trajectory.confidence is not None else np.ones(count)
    health = (
        trajectory.health.copy()
        if trajectory.health is not None
        else np.array([PoseHealth.OK.value] * count, dtype=object)
    )
    return Trajectory(
        timestamps=trajectory.timestamps.copy(),
        method=trajectory.method,
        positions=trajectory.positions.copy(),
        orientations=trajectory.orientations.copy(),
        velocities=trajectory.velocities.copy() if trajectory.velocities is not None else None,
        confidence=confidence,
        health=health,
        latency_ms=trajectory.latency_ms.copy() if trajectory.latency_ms is not None else None,
        extra_columns={name: values.copy() for name, values in trajectory.extra_columns.items()},
    )


def _ramp(timestamps: np.ndarray, perturbation: BackendPerturbation) -> np.ndarray:
    span = perturbation.t_end - perturbation.t_start
    return np.clip((timestamps - perturbation.t_start) / span, 0.0, 1.0)


def _quality_arrays(trajectory: Trajectory) -> tuple[np.ndarray, np.ndarray]:
    confidence = trajectory.confidence
    health = trajectory.health
    if confidence is None or health is None:
        raise ValueError("Perturbations require materialized confidence/health arrays")
    return confidence, health


def _unit_direction(perturbation: BackendPerturbation) -> np.ndarray:
    direction = np.asarray(perturbation.direction, dtype=np.float64)
    norm = np.linalg.norm(direction)
    if norm > 0.0:
        return direction / norm
    return np.array([1.0, 0.0, 0.0])


def _apply_dropout(confidence: np.ndarray, health: np.ndarray, mask: np.ndarray) -> None:
    health[mask] = PoseHealth.LOST.value
    confidence[mask] = 0.0


def _apply_noise_burst(
    trajectory: Trajectory, confidence: np.ndarray, mask: np.ndarray, perturbation: BackendPerturbation
) -> None:
    rng = np.random.Generator(np.random.PCG64(perturbation.seed))
    noise = rng.normal(0.0, perturbation.magnitude_m, size=(int(np.count_nonzero(mask)), 3))
    trajectory.positions[mask] += noise
    confidence[mask] *= _NOISE_CONFIDENCE_SCALE


def _apply_bias(
    trajectory: Trajectory, confidence: np.ndarray, mask: np.ndarray, perturbation: BackendPerturbation
) -> None:
    t = trajectory.timestamps
    direction = _unit_direction(perturbation)
    offset = perturbation.magnitude_m * _ramp(t[mask], perturbation)[:, np.newaxis] * direction[np.newaxis, :]
    trajectory.positions[mask] += offset
    if perturbation.kind == KIND_BIAS_RAMP:
        confidence[mask] *= _HONEST_BIAS_CONFIDENCE_SCALE
    # KIND_CONFIDENT_BIAS intentionally leaves confidence untouched: the backend lies.


def _apply_one(trajectory: Trajectory, perturbation: BackendPerturbation) -> None:
    confidence, health = _quality_arrays(trajectory)
    t = trajectory.timestamps
    mask = (t >= perturbation.t_start) & (t <= perturbation.t_end)
    if not np.any(mask):
        return
    if perturbation.kind == KIND_DROPOUT:
        _apply_dropout(confidence, health, mask)
        return
    if perturbation.kind == KIND_NOISE_BURST:
        _apply_noise_burst(trajectory, confidence, mask, perturbation)
        return
    _apply_bias(trajectory, confidence, mask, perturbation)


def apply_perturbations(trajectory: Trajectory, perturbations: list[BackendPerturbation]) -> Trajectory:
    """Return a deep-copied trajectory with all matching perturbations applied."""
    result = _copied_trajectory(trajectory)
    for perturbation in perturbations:
        if perturbation.method == trajectory.method:
            _apply_one(result, perturbation)
    return result


def _sample_window(rng: np.random.Generator, t_start: float, t_end: float) -> tuple[float, float]:
    span = t_end - t_start
    length = float(rng.uniform(0.2, 0.4)) * span
    start = t_start + float(rng.uniform(0.0, max(span - length, 1e-9)))
    return start, start + length


def _sample_one(
    rng: np.random.Generator, methods: tuple[str, ...], t_start: float, t_end: float, severity: int
) -> BackendPerturbation:
    method = str(rng.choice(list(methods)))
    kind = str(rng.choice(list(PERTURBATION_KINDS)))
    window_start, window_end = _sample_window(rng, t_start, t_end)
    magnitude = float(rng.uniform(0.5, 1.5)) * severity if kind != KIND_NOISE_BURST else 0.15 * severity
    direction = rng.normal(size=3)
    return BackendPerturbation(
        method=method,
        kind=kind,
        t_start=window_start,
        t_end=window_end,
        magnitude_m=magnitude,
        direction=(float(direction[0]), float(direction[1]), float(direction[2])),
        seed=int(rng.integers(0, 2**31 - 1)),
    )


def _should_sample(severity: int, methods: tuple[str, ...], t_start: float, t_end: float) -> bool:
    if severity < 0:
        raise ValueError("severity must be non-negative")
    return severity > 0 and bool(methods) and t_end > t_start


def sample_episode_perturbations(
    rng: np.random.Generator,
    methods: tuple[str, ...],
    t_start: float,
    t_end: float,
    severity: int,
) -> list[BackendPerturbation]:
    """Draw ``severity`` seeded degradations for one episode (severity 0 = clean)."""
    if not _should_sample(severity, methods, t_start, t_end):
        return []
    return [_sample_one(rng, methods, t_start, t_end, severity) for _ in range(severity)]
