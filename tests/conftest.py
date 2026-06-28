"""Shared fixtures for synthetic-sequence tests.

Builds a tiny, fully-formed sequence on disk via the real pipeline (no Google Earth, OpenCV,
or ffmpeg) so loader/validation tests can run against realistic artifacts. Previews are not
required for the tiny config because mp4 encoding is unavailable in headless CI.
"""

import shutil
from pathlib import Path

import pytest

from nav_benchmark.synthetic.config import (
    CameraCfg,
    FlightCfg,
    HeadingPoint,
    RecordingCfg,
    SequenceCfg,
    SequenceConfig,
    ValidationCfg,
)
from nav_benchmark.synthetic.pipeline import build_sequence


def tiny_config() -> SequenceConfig:
    """A small deterministic config: 64x48, ~0.4 s, with a straight + turn heading script."""
    return SequenceConfig(
        sequence=SequenceCfg(name="tiny", duration_s=0.4, random_seed=7),
        recording=RecordingCfg(capture_fps=30.0, save_rgb_preview=False, preview_fps=10.0),
        flight=FlightCfg(
            speed_mps=10.0,
            heading_script=[
                HeadingPoint(0.0, 90.0),
                HeadingPoint(0.2, 120.0),
                HeadingPoint(0.4, 120.0),
            ],
        ),
        camera=CameraCfg(width=64, height=48),
        validation=ValidationCfg(require_rgb_preview=False, require_event_preview=False),
    )


@pytest.fixture(scope="session")
def tiny_sequence(tmp_path_factory) -> Path:
    """Build the tiny sequence once per session; treat the returned directory as read-only."""
    out = tmp_path_factory.mktemp("ge_tiny")
    config = tiny_config()
    build_sequence(config, out, source="synthetic", add_imu_noise=False, log=lambda _m: None)
    return out


@pytest.fixture
def mutable_sequence(tiny_sequence: Path, tmp_path: Path) -> Path:
    """A fresh writable copy of the tiny sequence for tests that corrupt files."""
    dst = tmp_path / "seq"
    shutil.copytree(tiny_sequence, dst)
    return dst


@pytest.fixture
def tiny_cfg() -> SequenceConfig:
    """Config matching the tiny sequence (64x48, previews not required)."""
    return tiny_config()
