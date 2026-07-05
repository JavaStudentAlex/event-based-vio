import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from nav_benchmark.baselines.external import ExternalTrajectoryBackend, ExternalTrajectoryConfig
from nav_benchmark.datasets.mvsec import Calibration, LoadDiagnostics, MvsecSequence, SequenceMetadata
from nav_benchmark.trajectory.export import export_project_csv, export_tum, read_tum_trajectory
from nav_benchmark.trajectory.models import Trajectory


def _empty_sequence() -> MvsecSequence:
    return MvsecSequence(
        metadata=SequenceMetadata(source_path="none", sequence_name="none"),
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(),
    )


def _sample_trajectory(method: str = "external") -> Trajectory:
    timestamps = np.array([0.0, 0.1, 0.2, 1.0])
    positions = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.2, 0.0, 0.0], [1.0, 0.0, 0.0]])
    orientations = np.array([[0.0, 0.0, 0.0, 1.0]] * 4)
    return Trajectory(timestamps=timestamps, method=method, positions=positions, orientations=orientations)


class TestReadTumTrajectory:
    def test_round_trip_through_export(self, tmp_path):
        original = _sample_trajectory()
        tum_path = tmp_path / "traj.tum"
        export_tum(original, tum_path)

        loaded = read_tum_trajectory(tum_path)

        np.testing.assert_allclose(loaded.timestamps, original.timestamps)
        np.testing.assert_allclose(loaded.positions, original.positions)
        np.testing.assert_allclose(loaded.orientations, original.orientations)
        assert loaded.method == "external"

    def test_skips_comments_and_blank_lines(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        tum_path.write_text("# header\n\n1.0 0 0 0 0 0 0 1\n2.0 1 0 0 0 0 0 1\n", encoding="utf-8")

        loaded = read_tum_trajectory(tum_path)
        assert len(loaded.timestamps) == 2
        assert loaded.positions[1, 0] == 1.0

    def test_rejects_wrong_field_count(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        tum_path.write_text("1.0 0 0 0 0 0 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="expected 8"):
            read_tum_trajectory(tum_path)

    def test_rejects_non_numeric_field(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        tum_path.write_text("1.0 0 0 zero 0 0 0 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="non-numeric"):
            read_tum_trajectory(tum_path)

    def test_rejects_non_monotonic_timestamps(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        tum_path.write_text("2.0 0 0 0 0 0 0 1\n1.0 0 0 0 0 0 0 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="strictly increasing"):
            read_tum_trajectory(tum_path)

    def test_rejects_empty_file(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        tum_path.write_text("# only comments\n", encoding="utf-8")
        with pytest.raises(ValueError, match="no pose rows"):
            read_tum_trajectory(tum_path)


class TestExternalTrajectoryBackend:
    def test_tum_input_gets_confidence_and_gap_health(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        export_tum(_sample_trajectory(), tum_path)

        config = ExternalTrajectoryConfig(trajectory_path=tum_path, default_confidence=0.7, gap_degraded_sec=0.5)
        trajectory = ExternalTrajectoryBackend().run(_empty_sequence(), config=config)

        assert trajectory.method == "external"
        np.testing.assert_allclose(trajectory.confidence, 0.7)
        # The 0.2 -> 1.0 jump exceeds the 0.5 s gap threshold.
        assert list(trajectory.health) == ["OK", "OK", "OK", "DEGRADED"]

    def test_csv_input_keeps_file_health_and_relabels_method(self, tmp_path):
        source = _sample_trajectory(method="ultimate_slam")
        source.health = np.array(["OK", "DEGRADED", "OK", "LOST"], dtype=object)
        source.confidence = np.array([1.0, 0.5, 0.9, 0.1])
        csv_path = tmp_path / "traj.csv"
        export_project_csv(source, csv_path)

        config = ExternalTrajectoryConfig(trajectory_path=csv_path)
        trajectory = ExternalTrajectoryBackend().run(_empty_sequence(), config=config)

        assert trajectory.method == "external"
        assert list(trajectory.health) == ["OK", "DEGRADED", "OK", "LOST"]
        np.testing.assert_allclose(trajectory.confidence, [1.0, 0.5, 0.9, 0.1])

    def test_format_auto_detection_by_extension(self, tmp_path):
        csv_path = tmp_path / "traj.csv"
        export_project_csv(_sample_trajectory(), csv_path)
        config = ExternalTrajectoryConfig(trajectory_path=csv_path, format="auto")
        trajectory = ExternalTrajectoryBackend().run(_empty_sequence(), config=config)
        assert len(trajectory.timestamps) == 4

    def test_requires_config_with_path(self):
        with pytest.raises(ValueError, match="trajectory_path"):
            ExternalTrajectoryBackend().run(_empty_sequence(), config=None)

    def test_missing_file_raises(self, tmp_path):
        config = ExternalTrajectoryConfig(trajectory_path=tmp_path / "missing.tum")
        with pytest.raises(FileNotFoundError):
            ExternalTrajectoryBackend().run(_empty_sequence(), config=config)

    def test_unsupported_format_raises(self, tmp_path):
        tum_path = tmp_path / "traj.tum"
        export_tum(_sample_trajectory(), tum_path)
        config = ExternalTrajectoryConfig(trajectory_path=tum_path, format="bag")
        with pytest.raises(ValueError, match="Unsupported external trajectory format"):
            ExternalTrajectoryBackend().run(_empty_sequence(), config=config)


def test_external_method_cli_produces_validated_run(tmp_path):
    from nav_benchmark.run import main

    tum_path = tmp_path / "external.tum"
    export_tum(_sample_trajectory(), tum_path)
    output_root = tmp_path / "runs"

    run_argv = [
        "nav_benchmark.run",
        "run",
        "--method",
        "external",
        "--dataset",
        "synthetic",
        "--sequence",
        "ext_demo",
        "--external-trajectory",
        str(tum_path),
        "--output-root",
        str(output_root),
    ]
    with mock.patch.object(sys, "argv", run_argv):
        main()

    run_dirs = list(output_root.glob("*_external_ext_demo"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "estimated_trajectory.csv").exists()

    validate_argv = ["nav_benchmark.run", "validate", "--run-dir", str(run_dir), "--skip-eval"]
    with mock.patch.object(sys, "argv", validate_argv):
        main()

    import json

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["method"] == "external"
    assert manifest["frames"]["source"] == "external"
    assert manifest["config"]["trajectory_path"] == str(tum_path)


def test_external_method_requires_trajectory_argument(tmp_path):
    from nav_benchmark.run import main

    argv = [
        "nav_benchmark.run",
        "run",
        "--method",
        "external",
        "--dataset",
        "synthetic",
        "--sequence",
        "ext_missing",
        "--output-root",
        str(tmp_path / "runs"),
    ]
    with mock.patch.object(sys, "argv", argv), pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 2


def test_external_config_path_survives_json_serialization(tmp_path):
    from nav_benchmark.evaluation.metrics import make_json_serializable

    config = ExternalTrajectoryConfig(trajectory_path=Path("/tmp/x.tum"))
    serialized = make_json_serializable(config)
    assert serialized["trajectory_path"] == "/tmp/x.tum"
    assert serialized["format"] == "auto"
