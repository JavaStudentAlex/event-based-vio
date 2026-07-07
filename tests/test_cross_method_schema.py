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
from nav_benchmark.trajectory.export import PROJECT_TRAJECTORY_COLUMNS, export_project_csv, export_tum
from nav_benchmark.trajectory.models import PoseHealth, Trajectory
from nav_benchmark.validation import validate_run_directory

EXPECTED_RUN_ARTIFACTS = {
    "estimated_trajectory.csv",
    "estimated_trajectory_tum.txt",
    "failure_notes.md",
    "run.log",
    "run_manifest.json",
}
ALLOWED_HEALTH_LABELS = {state.value for state in PoseHealth}


def _synthetic_sequence() -> MvsecSequence:
    timestamps = np.linspace(0.0, 0.5, 6, dtype=np.float64)

    imu = np.zeros(len(timestamps), dtype=IMU_DTYPE)
    imu["t"] = timestamps
    imu["az"] = 9.81

    gt_poses = np.zeros(len(timestamps), dtype=POSE_DTYPE)
    gt_poses["t"] = timestamps
    gt_poses["x"] = 0.1 * timestamps
    gt_poses["qw"] = 1.0

    images = np.stack([_textured_frame(shift=i) for i in range(len(timestamps))]).astype(np.uint8)
    event_frames = np.stack([_event_frame(shift=i) for i in range(len(timestamps))]).astype(np.uint8)
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
            source_path="synthetic://cross_method_schema",
            sequence_name="cross_method_schema",
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


def _textured_frame(*, shift: int, size: int = 32) -> np.ndarray:
    frame = np.zeros((size, size), dtype=np.uint8)
    frame[6 + shift : 14 + shift, 7:15] = 220
    frame[18:26, 17 + shift : 25 + shift] = 180
    frame[::4, :] = np.maximum(frame[::4, :], 45)
    frame[:, ::5] = np.maximum(frame[:, ::5], 35)
    return frame


def _event_frame(*, shift: int, size: int = 32) -> np.ndarray:
    frame = np.zeros((2, size, size), dtype=np.uint8)
    frame[0, 8 + shift : 16 + shift, 9:17] = 1
    frame[1, 19:25, 18 + shift : 24 + shift] = 1
    return frame


def _synthetic_events(timestamps: np.ndarray) -> np.ndarray:
    events = np.zeros(len(timestamps) * 8, dtype=EVENT_DTYPE)
    for frame_index, ts in enumerate(timestamps):
        start = frame_index * 8
        for offset in range(8):
            row = start + offset
            events["t"][row] = ts + offset * 1e-4
            events["x"][row] = 8 + frame_index + offset
            events["y"][row] = 10 + offset
            events["p"][row] = 1 if offset % 2 == 0 else -1
    return events


def _run_methods(sequence: MvsecSequence) -> dict[str, Trajectory]:
    imu_config = ImuOnlyConfig(gravity=np.array([0.0, 0.0, 9.81], dtype=np.float64))
    backends = [ImuOnlyBackend(), EventImuBackend(), ImageImuBackend()]
    trajectories: dict[str, Trajectory] = {}
    for backend in backends:
        config = imu_config if backend.method == "imu_only" else None
        result = backend.run_result(sequence, config=config)
        trajectories[backend.method] = result.trajectory
    return trajectories


def _write_run_directory(run_dir: Path, trajectory: Trajectory, sequence: MvsecSequence) -> None:
    run_dir.mkdir(parents=True)
    export_project_csv(trajectory, run_dir / "estimated_trajectory.csv")
    export_tum(trajectory, run_dir / "estimated_trajectory_tum.txt")
    health_counts = _health_counts(trajectory)
    _write_manifest(run_dir / "run_manifest.json", trajectory.method, sequence, health_counts)
    _write_failure_notes(run_dir / "failure_notes.md", health_counts)
    (run_dir / "run.log").write_text(f"method={trajectory.method} status=success\n", encoding="utf-8")


def _health_counts(trajectory: Trajectory) -> dict[str, int]:
    counts = {state.value: 0 for state in PoseHealth}
    labels = trajectory.health if trajectory.health is not None else [PoseHealth.OK.value] * len(trajectory.timestamps)
    for label in labels:
        counts[str(label)] += 1
    return counts


def _write_manifest(
    path: Path,
    method: str,
    sequence: MvsecSequence,
    health_counts: dict[str, int],
) -> None:
    manifest = {
        "method": method,
        "dataset": "synthetic",
        "sequence": sequence.metadata.sequence_name,
        "input": sequence.metadata.source_path,
        "config": {"fixture": "cross_method_schema"},
        "timestamp_policy": "seconds",
        "gravity": [0.0, 0.0, 9.81],
        "frames": {"body": "imu", "world": "world"},
        "units": {"position": "meters", "orientation": "quaternion_xyzw", "latency": "milliseconds"},
        "alignment": {"policy": "none"},
        "code_version": "test",
        "status": "success",
        "health_counts": health_counts,
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _write_failure_notes(path: Path, health_counts: dict[str, int]) -> None:
    failure_count = health_counts[PoseHealth.DEGRADED.value] + health_counts[PoseHealth.LOST.value]
    failure_count += health_counts[PoseHealth.INVALID.value]
    if failure_count == 0:
        detail = "No degraded or lost intervals were detected."
    else:
        detail = f"Detected {failure_count} degraded, lost, or invalid samples."
    path.write_text(
        "# Run Failure Notes\n\n"
        "## Health Summary\n\n"
        f"{json.dumps(health_counts, sort_keys=True)}\n\n"
        "## Detected Degraded/Lost Intervals\n\n"
        f"{detail}\n",
        encoding="utf-8",
    )


def _csv_header_and_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def test_imu_event_imu_and_image_imu_emit_matching_run_artifact_schema(tmp_path):
    sequence = _synthetic_sequence()
    trajectories = _run_methods(sequence)

    run_dirs = {}
    for method, trajectory in trajectories.items():
        run_dir = tmp_path / method
        _write_run_directory(run_dir, trajectory, sequence)
        run_dirs[method] = run_dir

    artifact_sets = {method: {path.name for path in run_dir.iterdir()} for method, run_dir in run_dirs.items()}
    assert set(artifact_sets) == {"imu_only", "event_imu", "image_imu"}
    assert all(artifacts == EXPECTED_RUN_ARTIFACTS for artifacts in artifact_sets.values())

    csv_headers = {}
    for method, run_dir in run_dirs.items():
        results, passed = validate_run_directory(run_dir, expect_eval=False)
        assert passed, f"{method} validation failed: {[r for r in results if not r.passed]}"

        header, rows = _csv_header_and_rows(run_dir / "estimated_trajectory.csv")
        csv_headers[method] = header
        assert header == PROJECT_TRAJECTORY_COLUMNS
        assert rows, f"{method} trajectory CSV has no data rows"
        assert {row["method"] for row in rows} == {method}
        assert {row["health"] for row in rows} <= ALLOWED_HEALTH_LABELS

    assert len({tuple(header) for header in csv_headers.values()}) == 1
