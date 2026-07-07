import csv
import json
from pathlib import Path

import numpy as np

from nav_benchmark.baselines.event_imu import EventImuBackend
from nav_benchmark.baselines.image_imu import ImageImuBackend
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.datasets.mvsec import (
    EVENT_DTYPE,
    IMU_DTYPE,
    POSE_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
)
from nav_benchmark.evaluation.harness import evaluate_run_directory
from nav_benchmark.reporting.compare import compare_runs, write_comparison_artifacts
from nav_benchmark.trajectory.export import export_project_csv, export_tum
from nav_benchmark.trajectory.models import PoseHealth

def _event_rich_synthetic_sequence() -> MvsecSequence:
    """Create a synthetic sequence with clear lateral drift and strong event cues."""
    num_frames = 100
    duration = 2.0
    timestamps = np.linspace(0.0, duration, num_frames, dtype=np.float64)
    dt = timestamps[1] - timestamps[0]

    imu = np.zeros(num_frames, dtype=IMU_DTYPE)
    imu["t"] = timestamps
    # Need a consistent motion that event_imu will pick up to offset imu drift
    # Let's say constant velocity in X
    velocity_x = 2.0

    # Let IMU have bias in X so it drifts
    imu["ax"] = 1.0
    np.random.seed(42)
    imu["ax"] += np.random.normal(0, 0.5, num_frames)
    imu["ay"] = np.sin(timestamps * 2.0)
    imu["az"] = 9.81 + np.cos(timestamps * 3.0)

    # GT must have 3D variation to prevent umeyama failure due to collinear points.
    gt_poses = np.zeros(num_frames, dtype=POSE_DTYPE)
    gt_poses["t"] = timestamps

    gt_poses["x"] = velocity_x * timestamps
    gt_poses["y"] = 0.5 * np.cos(timestamps * 2.0) - 0.5 # start at 0
    gt_poses["z"] = 0.5 * np.sin(timestamps * 3.0)
    gt_poses["qw"] = 1.0

    # For event_imu to correct X drift, the event frames must shift in X proportional to velocity
    # If the camera moves forward by V*dt, the image shifts left or right.
    # We will simulate a continuous shift in the image plane

    # Frames that show a clear shift (dx) for event correlation
    images = np.stack([_textured_frame(shift=timestamps[i] * 50) for i in range(num_frames)]).astype(np.uint8)
    event_frames = np.stack([_event_frame(shift=timestamps[i] * 50) for i in range(num_frames)]).astype(np.uint8)
    events = _synthetic_events(timestamps)

    sample_counts = {
        "imu": len(imu),
        "gt_poses": len(gt_poses),
        "images": len(images),
        "event_frames": len(event_frames),
        "events": len(events),
    }
    time_ranges = {name: (float(timestamps[0]), float(timestamps[-1])) for name in sample_counts}

    return MvsecSequence(
        metadata=SequenceMetadata(
            source_path="synthetic://benchmark_comparison",
            sequence_name="benchmark_comparison",
            time_ranges=time_ranges,
            sample_counts=sample_counts,
        ),
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(
            intrinsics_available=True,
            data={"K": np.array([[120.0, 0.0, 16.0], [0.0, 120.0, 16.0], [0.0, 0.0, 1.0]])},
        ),
        events=events,
        imu=imu,
        gt_poses=gt_poses,
        images=images,
        image_timestamps=timestamps,
        event_frames=event_frames,
        event_frame_timestamps=timestamps,
    )

def _textured_frame(*, shift: float, size: int = 64) -> np.ndarray:
    frame = np.zeros((size, size), dtype=np.uint8)
    s = int(shift) % 32
    frame[16:32, 18 + s : 34 + s] = 220
    frame[38:50, 36 - s : 48 - s] = 180
    frame[::4, :] = np.maximum(frame[::4, :], 45)
    frame[:, ::5] = np.maximum(frame[:, ::5], 35)
    return frame

def _event_frame(*, shift: float, size: int = 64) -> np.ndarray:
    # the shift estimation code uses shape (H, W) or (H, W, 3).
    # Since our sequence stores event_frames of shape (H, W) for synthetic tests
    # let's just make it (H, W)
    frame = np.zeros((size, size), dtype=np.uint8)
    s = int(shift) % 32
    frame[16:32, 18 + s : 34 + s] = 1
    # Note: don't make multiple moving blocks with opposite shifts, because shift estimation
    # uses phase correlation which might fail or get confused. Let's make only one block.
    # frame[38:50, 36 - s : 48 - s] = 1
    return frame

def _synthetic_events(timestamps: np.ndarray) -> np.ndarray:
    events = np.zeros(len(timestamps) * 8, dtype=EVENT_DTYPE)
    for frame_index, ts in enumerate(timestamps):
        start = frame_index * 8
        for offset in range(8):
            row = start + offset
            events["t"][row] = ts + offset * 1e-4
            events["x"][row] = (8 + frame_index + offset) % 64
            events["y"][row] = (10 + offset) % 64
            events["p"][row] = 1 if offset % 2 == 0 else -1
    return events


def test_benchmark_comparison_event_imu_vs_imu_only(tmp_path):
    # 1. Generate sequence
    sequence = _event_rich_synthetic_sequence()

    # Run backends
    backends = [
        ("imu_only", ImuOnlyBackend()),
        ("event_imu", EventImuBackend()),
        ("image_imu", ImageImuBackend())
    ]

    run_dirs = []

    for method, backend in backends:
        run_dir = tmp_path / method
        run_dir.mkdir()
        run_dirs.append(run_dir)

        # Run backend
        config = None
        if method == "imu_only":
            config = ImuOnlyConfig(gravity=np.array([0.0, 0.0, 9.81], dtype=np.float64))
        result = backend.run_result(sequence, config=config)
        trajectory = result.trajectory

        # Export trajectory
        export_project_csv(trajectory, run_dir / "estimated_trajectory.csv")
        export_tum(trajectory, run_dir / "estimated_trajectory_tum.txt")

        # Write minimal manifest for harness
        manifest = {
            "method": method,
            "dataset": "synthetic",
            "sequence": sequence.metadata.sequence_name,
            "input": sequence.metadata.source_path,
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        # Write ground truth for harness to find
        gt_dir = run_dir / "ground_truth"
        gt_dir.mkdir()
        export_project_csv(_gt_trajectory(sequence), gt_dir / "trajectory.csv")

        # Evaluate
        evaluate_run_directory(run_dir, ground_truth_path=gt_dir / "trajectory.csv")

    # 2. Compare runs
    summaries = compare_runs(run_dirs)

    # 3. Write comparison artifacts
    comparison_dir = tmp_path / "comparison"
    artifacts = write_comparison_artifacts(summaries, comparison_dir)

    # 4. Assertions
    # Artifacts exist and are non-empty
    assert (comparison_dir / "metrics_comparison.json").exists()
    assert (comparison_dir / "metrics_comparison.json").stat().st_size > 0
    assert (comparison_dir / "comparison_table.csv").exists()
    assert (comparison_dir / "comparison_table.csv").stat().st_size > 0
    assert (comparison_dir / "backend_comparison_drift.png").exists()
    assert (comparison_dir / "backend_comparison_drift.png").stat().st_size > 0

    summary_map = {s.method: s for s in summaries}

    event_imu_summary = summary_map["event_imu"]
    imu_only_summary = summary_map["imu_only"]
    image_imu_summary = summary_map["image_imu"]

    assert image_imu_summary.ate_rmse is not None
    assert event_imu_summary.ate_rmse is not None
    assert imu_only_summary.ate_rmse is not None

    print(f"event_imu ATE: {event_imu_summary.ate_rmse}, imu_only ATE: {imu_only_summary.ate_rmse}")
    assert event_imu_summary.ate_rmse < imu_only_summary.ate_rmse


def _gt_trajectory(sequence: MvsecSequence):
    from nav_benchmark.trajectory.models import Trajectory

    count = len(sequence.gt_poses)
    return Trajectory(
        timestamps=sequence.gt_poses["t"],
        method="ground_truth",
        positions=np.stack([sequence.gt_poses["x"], sequence.gt_poses["y"], sequence.gt_poses["z"]], axis=1),
        orientations=np.stack([sequence.gt_poses["qx"], sequence.gt_poses["qy"], sequence.gt_poses["qz"], sequence.gt_poses["qw"]], axis=1),
        velocities=np.zeros((count, 3), dtype=np.float64),
        confidence=np.ones(count, dtype=np.float64),
        health=np.array([PoseHealth.OK.value] * count, dtype=object),
        latency_ms=np.zeros(count, dtype=np.float64),
    )
