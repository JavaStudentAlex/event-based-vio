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

        # Time-varying accelerations so the integrated trajectory spans 3D
        # (SE(3) Umeyama alignment needs non-degenerate covariance).
        grp_imu = f.create_group("/davis/left/imu")
        grp_imu.create_dataset("ts", data=imu_t)
        grp_imu.create_dataset("linear_acceleration_x", data=np.sin(2.0 * np.pi * imu_t))
        grp_imu.create_dataset("linear_acceleration_y", data=np.cos(2.0 * np.pi * imu_t))
        grp_imu.create_dataset("linear_acceleration_z", data=9.81 + 0.5 * np.sin(4.0 * np.pi * imu_t))
        grp_imu.create_dataset("angular_velocity_x", data=np.zeros_like(imu_t))
        grp_imu.create_dataset("angular_velocity_y", data=np.zeros_like(imu_t))
        grp_imu.create_dataset("angular_velocity_z", data=np.zeros_like(imu_t))

        grp_pose = f.create_group("/davis/left/pose")
        grp_pose.create_dataset("ts", data=imu_t)
        grp_pose.create_dataset("px", data=np.linspace(0.0, 1.0, 11))
        grp_pose.create_dataset("py", data=0.3 * np.sin(2.0 * np.pi * imu_t))
        grp_pose.create_dataset("pz", data=0.2 * np.sin(np.pi * imu_t))
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


def test_event_imu_run_evaluate_validate_full_artifact_set(mvsec_h5: Path, tmp_path: Path):
    """M002 acceptance: event_imu produces the full content-valid artifact set."""
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
            "--evaluate",
        ]
    )

    run_dir = next(output_root.glob("*_event_imu_mini"))
    expected_artifacts = [
        "estimated_trajectory.csv",
        "estimated_trajectory_tum.txt",
        "ground_truth_aligned.csv",
        "metrics.json",
        "error_vs_time.csv",
        "error_vs_distance.csv",
        "trajectory_plot.png",
        "drift_plot.png",
        "run.log",
        "failure_notes.md",
        "run_manifest.json",
    ]
    for name in expected_artifacts:
        artifact = run_dir / name
        assert artifact.exists(), f"missing artifact: {name}"
        assert artifact.stat().st_size > 0, f"empty artifact: {name}"

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["status"] == "OK"
    assert metrics["metrics"]["ate_rmse"] is not None
    assert metrics["runtime"]["latency_mean_ms"] is not None

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["method"] == "event_imu"
    assert manifest["evaluation"]["status"] == "success"
    run_diagnostics = manifest["config"]["run_diagnostics"]
    assert run_diagnostics["event_pair_count"] == 9
    assert 0.0 < run_diagnostics["imu_samples_covered_fraction"] <= 1.0

    _run_cli(["validate", "--run-dir", str(run_dir)])


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
