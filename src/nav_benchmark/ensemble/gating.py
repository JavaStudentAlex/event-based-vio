"""Measurement gates and covariance mapping for ensemble fusion.

Every rejected update carries an explicit reason so fusion logs can explain
which measurement was dropped and why (never silently fuse or drop).
"""

from dataclasses import dataclass

import numpy as np

from nav_benchmark.trajectory.models import PoseHealth

REASON_HEALTH = "health_gate"
REASON_CONFIDENCE = "confidence_gate"
REASON_TIMESTAMP = "timestamp_gate"
REASON_MOTION_SANITY = "motion_sanity_gate"
REASON_MAHALANOBIS = "mahalanobis_gate"


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    reason: str | None = None


_ACCEPT = GateDecision(accepted=True, reason=None)


def health_gate(health: str) -> GateDecision:
    """Reject measurements from backends that report LOST or INVALID poses."""
    if health in (PoseHealth.LOST.value, PoseHealth.INVALID.value):
        return GateDecision(accepted=False, reason=REASON_HEALTH)
    return _ACCEPT


def confidence_gate(confidence: float, min_confidence: float) -> GateDecision:
    """Reject measurements whose reported confidence is below the fusion floor."""
    if confidence < min_confidence:
        return GateDecision(accepted=False, reason=REASON_CONFIDENCE)
    return _ACCEPT


def timestamp_gate(measurement_time: float, state_time: float, max_age_sec: float) -> GateDecision:
    """Reject measurements too far from the current fusion state time."""
    if abs(measurement_time - state_time) > max_age_sec:
        return GateDecision(accepted=False, reason=REASON_TIMESTAMP)
    return _ACCEPT


def motion_sanity_gate(position_jump_m: float, dt_sec: float, max_speed_mps: float) -> GateDecision:
    """Reject measurements implying a physically impossible velocity."""
    dt = max(dt_sec, 1e-3)
    if position_jump_m / dt > max_speed_mps:
        return GateDecision(accepted=False, reason=REASON_MOTION_SANITY)
    return _ACCEPT


def mahalanobis_gate(innovation: np.ndarray, innovation_covariance: np.ndarray, chi2_threshold: float) -> GateDecision:
    """Reject statistically inconsistent innovations via the chi-square test."""
    if mahalanobis_distance_squared(innovation, innovation_covariance) > chi2_threshold:
        return GateDecision(accepted=False, reason=REASON_MAHALANOBIS)
    return _ACCEPT


def mahalanobis_distance_squared(innovation: np.ndarray, innovation_covariance: np.ndarray) -> float:
    """Squared Mahalanobis distance of an innovation under its covariance."""
    e = np.asarray(innovation, dtype=np.float64)
    S = np.asarray(innovation_covariance, dtype=np.float64)
    return float(e @ np.linalg.solve(S, e))


def confidence_to_position_sigma(confidence: float, sigma_min: float, sigma_range: float) -> float:
    """Monotonic map from backend confidence in [0, 1] to a position measurement sigma.

    Confidence 1.0 gives ``sigma_min``; confidence 0.0 gives ``sigma_min + sigma_range``.
    """
    clipped = float(np.clip(confidence, 0.0, 1.0))
    return sigma_min + (1.0 - clipped) * sigma_range


def health_confidence_multiplier(health: str, degraded_multiplier: float) -> float:
    """Confidence multiplier for a health label: OK keeps 1.0, DEGRADED is downweighted, failed is 0."""
    if health == PoseHealth.OK.value:
        return 1.0
    if health == PoseHealth.DEGRADED.value:
        return degraded_multiplier
    return 0.0
