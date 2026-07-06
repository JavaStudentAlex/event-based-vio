"""Bridge for embeddings precomputed by open-source pretrained JEPA models.

Large pretrained JEPA releases (I-JEPA, V-JEPA 2) are torch models with
hundreds of millions of parameters; running them belongs in an offline step on
a GPU node. This adapter consumes their per-frame embeddings from a simple
file contract instead of importing their code:

- HDF5: datasets ``/times`` (N, seconds) and ``/embeddings`` (N, D)
- NPZ: arrays ``times`` and ``embeddings``

Without the paired predictor, surprise is approximated by the cosine change
rate of consecutive embeddings, which preserves the "how fast is the scene
deviating from smooth ego-motion" semantics the gating policy consumes.
"""

from pathlib import Path

import h5py
import numpy as np

from nav_benchmark.jepa.signals import FrameSignals, combine_stream_signals
from nav_benchmark.rl.features import JepaObsSeries


def load_external_embeddings(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Load (times, embeddings) from an external-embedding HDF5/NPZ file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"External embedding file not found: {path}")
    if path.suffix == ".npz":
        data = np.load(path)
        if "times" not in data or "embeddings" not in data:
            raise ValueError(f"{path} must contain 'times' and 'embeddings' arrays")
        times, embeddings = data["times"], data["embeddings"]
    else:
        with h5py.File(path, "r") as f:
            if "times" not in f or "embeddings" not in f:
                raise ValueError(f"{path} must contain '/times' and '/embeddings' datasets")
            times, embeddings = f["times"][:], f["embeddings"][:]
    times = np.asarray(times, dtype=np.float64).reshape(-1)
    embeddings = np.asarray(embeddings, dtype=np.float64)
    if embeddings.ndim != 2 or len(times) != len(embeddings):
        raise ValueError(f"{path}: embeddings must be (N, D) aligned with times (N,)")
    if len(times) > 1 and np.any(np.diff(times) < 0.0):
        raise ValueError(f"{path}: times must be monotonically non-decreasing")
    return times, embeddings


def signals_from_embeddings(times: np.ndarray, embeddings: np.ndarray) -> FrameSignals:
    """Surprise/embedding-speed signals from raw pretrained-model embeddings."""
    count = len(times)
    surprise = np.zeros(count, dtype=np.float64)
    speed = np.zeros(count, dtype=np.float64)
    if count >= 2:
        now = embeddings[:-1]
        nxt = embeddings[1:]
        norms = np.linalg.norm(now, axis=1) * np.linalg.norm(nxt, axis=1)
        cosine = np.sum(now * nxt, axis=1) / np.where(norms > 0.0, norms, 1.0)
        surprise[1:] = 1.0 - np.clip(cosine, -1.0, 1.0)
        speed[1:] = np.linalg.norm(nxt - now, axis=1) / np.sqrt(embeddings.shape[1])
    return FrameSignals(times=times, surprise=surprise, embedding_speed=speed)


def obs_series_from_files(
    rgb_path: str | Path | None = None,
    event_path: str | Path | None = None,
) -> JepaObsSeries:
    """Observation series built entirely from precomputed pretrained embeddings."""
    if rgb_path is None and event_path is None:
        raise ValueError("At least one of rgb_path/event_path is required")
    rgb = signals_from_embeddings(*load_external_embeddings(rgb_path)) if rgb_path is not None else None
    event = signals_from_embeddings(*load_external_embeddings(event_path)) if event_path is not None else None
    return combine_stream_signals(rgb, event)
