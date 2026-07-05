"""CLI proof that raw MVSEC events are turned into event frames for event-based methods."""

import json
import sys
from pathlib import Path
from unittest import mock

import h5py
import numpy as np
import pytest

from nav_benchmark.run import main, sequence_event_diagnostics


def _write_mvsec_h5(h5_path: Path, *, event_count: int = 400, duration_sec: float = 1.0) -> None:
    rng = np.random.default_rng(42)
    t = np.sort(rng.uniform(0.0, duration_sec, size=event_count))
    x = rng.integers(0, 8, size=event_count).astype(np.uint16)
    y = rng.integers(0, 8, size=event_count).astype(np.uint16)
    p = rng.choice(np.array([-1, 1], dtype=np.int8), size=event_count)

    imu_t = np.linspace(0.0, duration_sec, 11)
    with h5py.File(h5_path, "w") as f:
        grp_events = f.create_group("/davis/left/events")
        grp_events.create_dataset("ts", data=t)
        grp_events.create_dataset("x", data=x)
        grp_events.create_dataset("y", data=y)
        grp_events.create_dataset("p", data=p)

        grp_imu = f.create_group("/davis/left/imu")
        grp_imu.create_dataset("ts", data=imu_t)
        grp_imu.create_dataset("linear_acceleration_x", data=np.zeros_like(imu_t))
        grp_imu.create_dataset("linear_acceleration_y", data=np.zeros_like(imu_t))
        grp_imu.create_dataset("linear_acceleration_z", data=np.full_like(imu_t, 9.81))
        grp_imu.create_dataset("angular_velocity_x", data=np.zeros_like(imu_t))
        grp_imu.create_dataset("angular_velocity_y", data=np.zeros_like(imu_t))
        grp_imu.create_dataset("angular_velocity_z", data=np.zeros_like(imu_t))

        grp_pose = f.create_group("/davis/left/pose")
        grp_pose.create_dataset("ts", data=imu_t)
        grp_pose.create_dataset("px", data=np.linspace(0.0, 1.0, 11))
        grp_pose.create_dataset("py", data=np.zeros_like(imu_t))
        grp_pose.create_dataset("pz", data=np.zeros_like(imu_t))
        grp_pose.create_dataset("qx", data=np.zeros_like(imu_t))
        grp_pose.create_dataset("qy", data=np.zeros_like(imu_t))
        grp_pose.create_dataset("qz", data=np.zeros_like(imu_t))
        grp_pose.create_dataset("qw", data=np.ones_like(imu_t))


@pytest.fixture
def mvsec_h5(tmp_path: Path) -> Path:
    h5_path = tmp_path / "mini_mvsec.h5"
    _write_mvsec_h5(h5_path)
    return h5_path


def _run_cli(argv: list[str]) -> None:
    with mock.patch.object(sys, "argv", ["nav_benchmark.run", *argv]):
        main()


def test_event_imu_runs_on_raw_mvsec_events(mvsec_h5: Path, tmp_path: Path):
    output_root = tmp_path / "runs"
    _run_cli(
        [
            "run",
            "--method",
            "event_imu",
            "--dataset",
            "mvsec",
            "--sequence",
            "mini",
            "--input",
            str(mvsec_h5),
            "--output-root",
            str(output_root),
            "--event-window-ms",
            "100",
        ]
    )

    run_dirs = list(output_root.glob("*_event_imu_mini"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    assert (run_dir / "estimated_trajectory.csv").exists()
    log_text = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "Built 10 event frames from raw events" in log_text

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    diagnostics = manifest["event_diagnostics"]
    assert diagnostics["total_events"] == 400
    assert diagnostics["window_sec"] == pytest.approx(0.1)
    assert diagnostics["window_count"] == 10
    assert 0.0 < diagnostics["positive_fraction"] < 1.0
    assert diagnostics["active_pixel_fraction"] > 0.0


def test_manifest_omits_event_diagnostics_without_events(tmp_path: Path):
    output_root = tmp_path / "runs"
    _run_cli(
        [
            "run",
            "--method",
            "imu_only",
            "--dataset",
            "synthetic",
            "--sequence",
            "no_events",
            "--output-root",
            str(output_root),
        ]
    )

    run_dirs = list(output_root.glob("*_imu_only_no_events"))
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text(encoding="utf-8"))
    assert "event_diagnostics" not in manifest

    usage = manifest["resource_usage"]
    assert usage["cpu_user_sec"] > 0.0
    assert usage["max_rss_mb"] > 0.0
    assert usage["cpu_system_sec"] >= 0.0


def test_sequence_event_diagnostics_none_without_events(mvsec_h5: Path):
    from nav_benchmark.datasets.mvsec import load_mvsec_sequence

    sequence = load_mvsec_sequence(mvsec_h5)
    sequence.events = None
    assert sequence_event_diagnostics(sequence, window_sec=0.05) is None


def test_sequence_event_diagnostics_reports_starvation(mvsec_h5: Path):
    from nav_benchmark.datasets.mvsec import load_mvsec_sequence

    sequence = load_mvsec_sequence(mvsec_h5)
    diagnostics = sequence_event_diagnostics(sequence, window_sec=0.1)
    assert diagnostics is not None
    # 400 events over ~1 s is ~400 Hz, far below the 1 kHz default starvation threshold.
    assert diagnostics.starved is True
    assert diagnostics.total_events == 400
