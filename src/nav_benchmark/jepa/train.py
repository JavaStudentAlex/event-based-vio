"""Self-supervised JEPA pretraining over benchmark sequences (CLI: ``train-jepa``).

Builds consecutive-frame pair datasets from the RGB and/or event-frame streams
of one or more sequences (ego-motion conditioning from IMU-only propagation,
no ground truth needed), trains the JEPA-lite model, and writes a ``.pt``
checkpoint plus a JSON training summary.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from nav_benchmark.datasets.loading import default_gravity, load_sequence
from nav_benchmark.events import ensure_event_frames
from nav_benchmark.jepa.frames import ego_motion_features, stack_frame_patches
from nav_benchmark.jepa.model import JepaConfig, JepaModel, build_pair_dataset, train_jepa
from nav_benchmark.jepa.signals import imu_reference_trajectory, stream_arrays_for_sequence

STREAM_CHOICES = ("both", "rgb", "events")


@dataclass
class JepaTrainSpec:
    """Inputs and hyperparameters for one JEPA pretraining run."""

    dataset: str
    inputs: list[Path]
    output: Path
    streams: str = "both"
    steps: int = 500
    batch_size: int = 64
    lr: float = 1e-3
    embed_dim: int = 32
    hidden_dim: int = 64
    ema_tau: float = 0.995
    seed: int = 0
    device: str = "auto"
    event_window_ms: float = 50.0
    sequence_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.streams not in STREAM_CHOICES:
            raise ValueError(f"streams must be one of {STREAM_CHOICES}")
        if not self.inputs:
            raise ValueError("At least one --input sequence is required")


def _selected_streams(spec: JepaTrainSpec) -> tuple[str, ...]:
    if spec.streams == "both":
        return ("rgb", "events")
    return (spec.streams,)


def _collect_segments(spec: JepaTrainSpec, log) -> tuple[list[tuple[np.ndarray, np.ndarray]], list[str]]:
    segments: list[tuple[np.ndarray, np.ndarray]] = []
    used: list[str] = []
    gravity = default_gravity(spec.dataset)
    for index, input_path in enumerate(spec.inputs):
        name = spec.sequence_names[index] if index < len(spec.sequence_names) else Path(input_path).name
        sequence = load_sequence(spec.dataset, input_path, sequence_name=name)
        ensure_event_frames(sequence, window_sec=spec.event_window_ms / 1000.0)
        reference = imu_reference_trajectory(sequence, gravity)
        for stream in _selected_streams(spec):
            arrays = stream_arrays_for_sequence(sequence, stream)
            if arrays is None:
                log(f"Sequence {name}: stream '{stream}' unavailable, skipping")
                continue
            frames, times = arrays
            patches = stack_frame_patches(frames)
            ego = ego_motion_features(reference[0], reference[1], reference[2], times)
            segments.append((patches, ego))
            used.append(f"{name}:{stream}")
            log(f"Sequence {name}: stream '{stream}' contributes {len(frames) - 1} frame pairs")
    return segments, used


def run_jepa_training(spec: JepaTrainSpec, log=print) -> dict:
    """Train the JEPA-lite model and write checkpoint + summary; returns the summary."""
    segments, used = _collect_segments(spec, log)
    patches_now, patches_next, ego = build_pair_dataset(segments)
    config = JepaConfig(
        embed_dim=spec.embed_dim,
        hidden_dim=spec.hidden_dim,
        ema_tau=spec.ema_tau,
        lr=spec.lr,
        batch_size=spec.batch_size,
        steps=spec.steps,
        seed=spec.seed,
    )
    model = JepaModel(config)
    history = train_jepa(model, patches_now, patches_next, ego, device=spec.device, log=log)
    model.save(spec.output)

    tail = max(len(history) // 10, 1)
    summary = {
        "checkpoint": str(spec.output),
        "streams_used": used,
        "pair_count": len(patches_now),
        "steps": len(history),
        "first_loss": float(history[0]),
        "final_loss_mean": float(np.mean(history[-tail:])),
        "spec": {**asdict(spec), "inputs": [str(p) for p in spec.inputs], "output": str(spec.output)},
    }
    summary_path = Path(spec.output).with_name(Path(spec.output).stem + "_training.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log(f"JEPA checkpoint written to {spec.output} (summary: {summary_path})")
    return summary
