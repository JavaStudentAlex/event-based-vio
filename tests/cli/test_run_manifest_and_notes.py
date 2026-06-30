import json
from unittest import mock

import numpy as np

from nav_benchmark.baselines.imu import ImuOnlyConfig
from nav_benchmark.run import _export_ensemble_artifacts, main
from nav_benchmark.trajectory.models import Trajectory


def test_manifest_and_notes_generation(tmp_path):
    """
    Test that running CLI on synthetic sequence generates run_manifest.json and failure_notes.md
    with correct structure and non-empty contents.
    """
    output_root = tmp_path / "runs"
    test_args = [
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "manifest_test_seq",
        "--output-root",
        str(output_root),
    ]

    with mock.patch("sys.argv", test_args):
        main()

    # Find the output directory
    run_folders = list(output_root.glob("*_imu_only_manifest_test_seq"))
    assert len(run_folders) == 1
    run_dir = run_folders[0]

    manifest_path = run_dir / "run_manifest.json"
    failure_notes_path = run_dir / "failure_notes.md"

    # Assert presence
    assert manifest_path.exists()
    assert failure_notes_path.exists()

    # Assert non-emptiness
    assert manifest_path.stat().st_size > 0
    assert failure_notes_path.stat().st_size > 0

    # Parse and validate JSON structure of manifest
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Required top-level keys
    required_keys = [
        "method",
        "dataset",
        "sequence",
        "config",
        "timestamp_policy",
        "gravity",
        "frames",
        "units",
        "alignment",
        "code_version",
        "status",
        "health_counts",
    ]
    for key in required_keys:
        assert key in manifest, f"Manifest missing key: {key}"

    # Check contents
    assert manifest["method"] == "imu_only"
    assert manifest["dataset"] == "synthetic"
    assert manifest["sequence"] == "manifest_test_seq"
    assert manifest["status"] == "success"
    assert isinstance(manifest["gravity"], list)
    assert len(manifest["gravity"]) == 3
    assert manifest["gravity"] == [0.0, 0.0, 9.81]

    # Health counts check: synthetic run has 100 timesteps, all should be OK by default
    assert manifest["health_counts"].get("OK") == 100
    assert manifest["health_counts"].get("DEGRADED") == 0
    assert manifest["health_counts"].get("LOST") == 0
    assert manifest["health_counts"].get("INVALID") == 0

    # Validate failure notes content
    notes = failure_notes_path.read_text(encoding="utf-8")
    assert "# Run Failure Notes" in notes
    assert "Health Summary" in notes
    assert "OK**: 100" in notes
    assert "DEGRADED**: 0" in notes
    assert "LOST**: 0" in notes
    assert "INVALID**: 0" in notes
    assert "No degraded or lost intervals were detected" in notes
    assert "IMU-only propagation accumulates integration drift rapidly" in notes


def test_manifest_and_notes_with_degraded_lost_transitions(tmp_path):
    """
    Test manifest and failure_notes generation when the sequence actually has
    degraded and lost states. Mocks ImuOnlyConfig to trigger thresholds earlier.
    """
    output_root = tmp_path / "runs"
    test_args = [
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "transition_test_seq",
        "--output-root",
        str(output_root),
    ]

    # Custom configuration with low time thresholds to trigger transitions
    # N = 100, t goes from 0.0 to 0.99.
    # degraded at >0.2s, lost at >0.5s
    def mock_config():
        return ImuOnlyConfig(
            gravity=np.array([0.0, 0.0, 9.81]),
            initial_position=np.array([0.0, 0.0, 0.0]),
            initial_orientation=np.array([0.0, 0.0, 0.0, 1.0]),
            initial_velocity=np.array([0.0, 0.0, 0.0]),
            degraded_time_threshold=0.2,
            lost_time_threshold=0.5,
            degraded_drift_threshold=50.0,
            lost_drift_threshold=100.0,
        )

    with mock.patch("sys.argv", test_args), mock.patch("nav_benchmark.run.ImuOnlyConfig", side_effect=mock_config):
        main()

    # Find the output directory
    run_folders = list(output_root.glob("*_imu_only_transition_test_seq"))
    assert len(run_folders) == 1
    run_dir = run_folders[0]

    manifest_path = run_dir / "run_manifest.json"
    failure_notes_path = run_dir / "failure_notes.md"

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Health counts should reflect all three states
    counts = manifest["health_counts"]
    assert counts.get("OK") > 0
    assert counts.get("DEGRADED") > 0
    assert counts.get("LOST") > 0
    assert counts.get("INVALID") == 0

    # Ensure config values in manifest match the mocked config thresholds
    cfg_section = manifest["config"]
    assert cfg_section["degraded_time_threshold"] == 0.2
    assert cfg_section["lost_time_threshold"] == 0.5

    # Check failure notes has the expected intervals recorded
    notes = failure_notes_path.read_text(encoding="utf-8")
    assert "DEGRADED" in notes
    assert "LOST" in notes
    assert "duration" in notes
    assert "No degraded or lost intervals were detected" not in notes


def test_export_ensemble_artifacts_writes_weights_and_plot(tmp_path, monkeypatch):
    calls = []

    def fake_plot(trajectory, output_path, sequence):
        calls.append((trajectory.method, output_path, sequence))
        output_path.with_suffix(".png").write_bytes(b"plot")

    monkeypatch.setattr("nav_benchmark.run.write_ensemble_weight_plot", fake_plot)

    timestamps = np.array([0.0, 1.0])
    trajectory = Trajectory(
        timestamps=timestamps,
        method="ensemble",
        positions=np.zeros((2, 3)),
        orientations=np.array([[0.0, 0.0, 0.0, 1.0]] * 2),
        extra_columns={
            "w_imu": np.array([0.5, 0.4]),
            "w_rgb": np.array([0.1, 0.1]),
            "w_event": np.array([0.1, 0.1]),
            "w_event_imu": np.array([0.1, 0.1]),
            "w_image_imu": np.array([0.1, 0.15]),
            "w_multimodal": np.array([0.1, 0.15]),
        },
    )
    args = mock.Mock(sequence="unit_seq")
    messages = []

    _export_ensemble_artifacts(args, trajectory, tmp_path, messages.append)

    assert (tmp_path / "ensemble_weights.csv").exists()
    assert calls == [("ensemble", tmp_path / "ensemble_weights", "unit_seq")]
    assert any("Exported ensemble weights" in message for message in messages)
