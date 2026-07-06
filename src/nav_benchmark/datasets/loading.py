"""Uniform sequence loading for the training CLIs (mirrors ``run.py`` semantics)."""

from pathlib import Path

import numpy as np

from nav_benchmark.datasets.mvsec import MvsecSequence, load_mvsec_sequence
from nav_benchmark.datasets.synthetic import load_synthetic_sequence

DATASET_KINDS = ("synthetic", "mvsec")


def load_sequence(dataset: str, input_path: str | Path, sequence_name: str | None = None) -> MvsecSequence:
    """Load a generated synthetic directory or an MVSEC HDF5 file."""
    if dataset not in DATASET_KINDS:
        raise ValueError(f"Unknown dataset kind: {dataset!r} (expected one of {DATASET_KINDS})")
    if dataset == "synthetic":
        return load_synthetic_sequence(input_path, sequence_name=sequence_name)
    return load_mvsec_sequence(input_path)


def default_gravity(dataset: str) -> np.ndarray:
    """Gravity convention per dataset, matching the benchmark runner.

    Generated synthetic IMU reports accelerometer rest as -gravity; MVSEC uses
    the standard +9.81 z-up convention.
    """
    if dataset == "synthetic":
        return np.array([0.0, 0.0, -9.81], dtype=np.float64)
    return np.array([0.0, 0.0, 9.81], dtype=np.float64)
