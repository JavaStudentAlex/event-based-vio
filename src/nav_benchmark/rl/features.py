"""Observation construction for the RL gating policy.

Observations are causal: the policy deciding trust for control step ``k`` only
sees filter/measurement statistics from step ``k - 1`` and earlier. All
features are squashed to bounded ranges so one badly scaled signal cannot
dominate training, and the exact layout (method order, JEPA on/off) is stored
in policy checkpoints so training and inference can never silently disagree.
"""

from dataclasses import dataclass

import numpy as np

from nav_benchmark.ensemble.rl_gated import ControlStepSummary

PER_METHOD_FEATURES = (
    "available",
    "mean_confidence",
    "frac_degraded",
    "frac_failed",
    "innovation",
    "mahalanobis",
    "staleness",
    "accept_ratio",
)
GLOBAL_FEATURES = ("ekf_sigma", "speed", "progress", "prev_mean_trust")
JEPA_FEATURES = ("rgb_surprise", "event_surprise", "embedding_speed")


@dataclass(frozen=True)
class FeatureConfig:
    """Fixed observation layout shared between training and inference."""

    methods: tuple[str, ...]
    include_jepa: bool = False
    innovation_scale_m: float = 5.0
    staleness_horizon_sec: float = 5.0
    speed_scale_mps: float = 20.0

    def __post_init__(self) -> None:
        if not self.methods:
            raise ValueError("FeatureConfig requires at least one method")
        if list(self.methods) != sorted(self.methods):
            raise ValueError("FeatureConfig methods must be sorted for a stable layout")

    def to_metadata(self) -> dict:
        return {
            "methods": list(self.methods),
            "include_jepa": self.include_jepa,
            "innovation_scale_m": self.innovation_scale_m,
            "staleness_horizon_sec": self.staleness_horizon_sec,
            "speed_scale_mps": self.speed_scale_mps,
        }

    @staticmethod
    def from_metadata(data: dict) -> "FeatureConfig":
        return FeatureConfig(
            methods=tuple(data["methods"]),
            include_jepa=bool(data["include_jepa"]),
            innovation_scale_m=float(data["innovation_scale_m"]),
            staleness_horizon_sec=float(data["staleness_horizon_sec"]),
            speed_scale_mps=float(data["speed_scale_mps"]),
        )


def observation_dim(config: FeatureConfig) -> int:
    jepa = len(JEPA_FEATURES) if config.include_jepa else 0
    return len(config.methods) * len(PER_METHOD_FEATURES) + len(GLOBAL_FEATURES) + jepa


def feature_names(config: FeatureConfig) -> list[str]:
    names = [f"{method}.{feature}" for method in config.methods for feature in PER_METHOD_FEATURES]
    names.extend(f"global.{feature}" for feature in GLOBAL_FEATURES)
    if config.include_jepa:
        names.extend(f"jepa.{feature}" for feature in JEPA_FEATURES)
    return names


@dataclass(frozen=True)
class JepaObsSeries:
    """Per-frame JEPA signals sampled causally onto control-step boundaries."""

    times: np.ndarray
    rgb_surprise: np.ndarray
    event_surprise: np.ndarray
    embedding_speed: np.ndarray

    def at(self, query_time: float) -> np.ndarray:
        """Latest signal at or before ``query_time`` (zeros before the first frame)."""
        index = int(np.searchsorted(self.times, query_time, side="right")) - 1
        if index < 0:
            return np.zeros(3, dtype=np.float64)
        return np.array(
            [self.rgb_surprise[index], self.event_surprise[index], self.embedding_speed[index]],
            dtype=np.float64,
        )


def _squash(value: float, scale: float) -> float:
    return float(np.tanh(value / scale))


def _method_block(config: FeatureConfig, summary: ControlStepSummary, method: str) -> list[float]:
    stats = summary.stats[method]
    staleness = min(summary.last_accept_age_sec[method] / config.staleness_horizon_sec, 1.0)
    return [
        1.0 if stats.offered > 0 else 0.0,
        stats.mean_confidence,
        stats.frac_degraded,
        stats.frac_failed,
        _squash(stats.mean_innovation_m, config.innovation_scale_m),
        _squash(np.log1p(stats.mean_d2), 4.0),
        staleness,
        stats.accept_ratio,
    ]


def _global_block(config: FeatureConfig, summary: ControlStepSummary, progress: float, prev_trusts: np.ndarray) -> list:
    return [
        _squash(np.log1p(summary.ekf_position_sigma_m), 2.0),
        _squash(summary.ekf_speed_mps, config.speed_scale_mps),
        float(np.clip(progress, 0.0, 1.0)),
        float(np.mean(prev_trusts)),
    ]


def initial_observation(config: FeatureConfig) -> np.ndarray:
    """Neutral first observation before any control step has run."""
    obs = np.zeros(observation_dim(config), dtype=np.float64)
    prev_trust_index = len(config.methods) * len(PER_METHOD_FEATURES) + GLOBAL_FEATURES.index("prev_mean_trust")
    obs[prev_trust_index] = 1.0
    return obs


def build_observation(
    config: FeatureConfig,
    summary: ControlStepSummary,
    *,
    progress: float,
    prev_trusts: np.ndarray,
    jepa_point: np.ndarray | None = None,
) -> np.ndarray:
    """Observation for the decision following ``summary`` (bounded, fixed layout)."""
    if tuple(sorted(summary.stats)) != config.methods:
        raise ValueError(f"Summary methods {sorted(summary.stats)} do not match layout {list(config.methods)}")
    values: list[float] = []
    for method in config.methods:
        values.extend(_method_block(config, summary, method))
    values.extend(_global_block(config, summary, progress, np.asarray(prev_trusts, dtype=np.float64)))
    if config.include_jepa:
        point = jepa_point if jepa_point is not None else np.zeros(3, dtype=np.float64)
        values.extend(float(np.tanh(v)) for v in np.asarray(point, dtype=np.float64))
    return np.asarray(values, dtype=np.float64)
