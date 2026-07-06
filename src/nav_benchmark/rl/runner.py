"""Benchmark inference for the RL-gated ensemble fusion mode.

Drives :class:`GatedEkfFusionCore` with the deterministic (mode) action of a
trained PPO policy. The checkpoint's embedded feature metadata is validated
against the actual backend set, and JEPA-trained policies refuse to run
without their JEPA signal source, so a benchmark run can never silently use a
mismatched observation layout.
"""

import csv
import time
from pathlib import Path

import numpy as np

from nav_benchmark.ensemble.fusion import UpdateRecord
from nav_benchmark.ensemble.rl_gated import GatedEkfFusionCore, RlGatedFusionConfig
from nav_benchmark.rl.features import (
    FeatureConfig,
    JepaObsSeries,
    build_observation,
    initial_observation,
)
from nav_benchmark.rl.ppo import PpoAgent
from nav_benchmark.trajectory.models import Trajectory

POLICY_METADATA_VERSION = 1


def policy_feature_metadata(feature_config: FeatureConfig, fusion_config: RlGatedFusionConfig) -> dict:
    """Metadata embedded in policy checkpoints binding them to an obs layout."""
    return {
        "version": POLICY_METADATA_VERSION,
        "features": feature_config.to_metadata(),
        "control_period_sec": fusion_config.control_period_sec,
        "min_trust_to_apply": fusion_config.min_trust_to_apply,
    }


def restore_policy_configs(agent: PpoAgent) -> tuple[FeatureConfig, float, float]:
    """Recover the feature layout and fusion timing a policy was trained with."""
    metadata = agent.feature_metadata
    if not metadata or metadata.get("version") != POLICY_METADATA_VERSION:
        raise ValueError("Policy checkpoint is missing compatible feature metadata; retrain or convert it")
    feature_config = FeatureConfig.from_metadata(metadata["features"])
    return feature_config, float(metadata["control_period_sec"]), float(metadata["min_trust_to_apply"])


def _validated_feature_config(agent: PpoAgent, methods: tuple[str, ...], jepa_series) -> FeatureConfig:
    feature_config, _period, _min_trust = restore_policy_configs(agent)
    if feature_config.methods != methods:
        raise ValueError(
            f"Policy was trained on methods {list(feature_config.methods)} but the run provides {list(methods)}"
        )
    if feature_config.include_jepa and jepa_series is None:
        raise ValueError("Policy was trained with JEPA features; provide --jepa or --jepa-embeddings-* for this run")
    return feature_config


def run_rl_gated_fusion(
    imu: np.ndarray,
    backend_trajectories: dict[str, Trajectory],
    agent: PpoAgent,
    *,
    fusion_config: RlGatedFusionConfig,
    initial_position: np.ndarray,
    initial_velocity: np.ndarray,
    initial_orientation_xyzw: np.ndarray,
    jepa_series: JepaObsSeries | None = None,
) -> tuple[Trajectory, list[UpdateRecord], list[dict]]:
    """Fuse backend streams with policy-driven trust; returns trajectory, records, trust log."""
    methods = tuple(sorted(backend_trajectories))
    feature_config = _validated_feature_config(agent, methods, jepa_series)

    start_wall = time.perf_counter()
    core = GatedEkfFusionCore(
        imu,
        backend_trajectories,
        config=fusion_config,
        initial_position=initial_position,
        initial_velocity=initial_velocity,
        initial_orientation_xyzw=initial_orientation_xyzw,
    )
    observation = initial_observation(feature_config)
    trust_log: list[dict] = []
    for step in range(core.num_steps):
        action = np.clip(agent.act_deterministic(observation), 0.0, 1.0)
        summary = core.step(action)
        jepa_point = jepa_series.at(summary.end_time) if jepa_series is not None else None
        observation = build_observation(
            feature_config,
            summary,
            progress=(step + 1) / core.num_steps,
            prev_trusts=action,
            jepa_point=jepa_point,
        )
        trust_log.append(
            {
                "timestamp": summary.end_time,
                **{f"trust_{method}": float(action[i]) for i, method in enumerate(methods)},
            }
        )

    elapsed_ms = (time.perf_counter() - start_wall) * 1000.0
    trajectory, records = core.result(elapsed_ms_total=elapsed_ms)
    return trajectory, records, trust_log


def write_trust_log_csv(trust_log: list[dict], path: str | Path) -> None:
    """Write the per-control-step policy trust values to CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not trust_log:
        path.write_text("timestamp\n", encoding="utf-8")
        return
    columns = list(trust_log[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in trust_log:
            writer.writerow({key: f"{value:.9f}" if isinstance(value, float) else value for key, value in row.items()})
