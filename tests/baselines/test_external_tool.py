"""Tests for the subprocess-based external baseline adapter and dataset conversion."""

import json
import shlex
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from nav_benchmark.baselines.external import (
    ExternalToolBackend,
    ExternalToolConfig,
    ExternalToolError,
    run_external_tool,
)
from nav_benchmark.datasets.convert import export_sequence_streams
from nav_benchmark.datasets.mvsec import (
    EVENT_DTYPE,
    IMU_DTYPE,
    POSE_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
)

_PY = shlex.quote(sys.executable)

_TUM_CONTENT = "0.0 0 0 0 0 0 0 1\\n0.5 1 0 0 0 0 0 1\\n1.0 2 0 0 0 0 0 1\\n"


def _write_tum_command(path: Path) -> str:
    return f"{_PY} -c \"open({str(path)!r}, 'w').write('{_TUM_CONTENT}')\""


def _empty_sequence() -> MvsecSequence:
    return MvsecSequence(
        metadata=SequenceMetadata(source_path="none", sequence_name="none"),
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(),
    )


class TestRunExternalTool:
    def test_success_records_execution(self):
        config = ExternalToolConfig(command=f"{_PY} -c \"print('adapter ok')\"", tool_name="demo_tool")
        execution = run_external_tool(config)
        assert execution.returncode == 0
        assert execution.duration_sec > 0.0
        assert "adapter ok" in execution.stdout_tail
        assert execution.tool_name == "demo_tool"
        assert not execution.timed_out

    def test_nonzero_exit_raises_with_stderr_tail(self):
        command = f"{_PY} -c \"import sys; sys.stderr.write('boom\\n'); sys.exit(3)\""
        with pytest.raises(ExternalToolError, match="exit code 3") as excinfo:
            run_external_tool(ExternalToolConfig(command=command, tool_name="broken"))
        assert "boom" in excinfo.value.execution.stderr_tail
        assert excinfo.value.execution.returncode == 3

    def test_missing_binary_raises_setup_hint(self):
        config = ExternalToolConfig(command="definitely-not-installed-tool-xyz --run")
        with pytest.raises(ExternalToolError, match="not found"):
            run_external_tool(config)

    def test_timeout_raises_and_flags_execution(self):
        command = f'{_PY} -c "import time; time.sleep(30)"'
        with pytest.raises(ExternalToolError, match="timed out") as excinfo:
            run_external_tool(ExternalToolConfig(command=command, timeout_sec=0.5, tool_name="slow"))
        assert excinfo.value.execution.timed_out

    def test_empty_command_rejected(self):
        with pytest.raises(ValueError, match="command"):
            run_external_tool(ExternalToolConfig(command="  "))

    def test_version_probe_recorded(self):
        config = ExternalToolConfig(
            command=f"{_PY} -c \"print('x')\"",
            version_command=f"{_PY} --version",
        )
        execution = run_external_tool(config)
        assert execution.tool_version is not None
        assert execution.tool_version.startswith("Python")

    def test_version_probe_failure_is_not_fatal(self):
        config = ExternalToolConfig(
            command=f"{_PY} -c \"print('x')\"",
            version_command="definitely-not-installed-version-probe --version",
        )
        execution = run_external_tool(config)
        assert execution.tool_version is None
        assert execution.returncode == 0


class TestExternalToolBackend:
    def test_runs_tool_and_normalizes_trajectory(self, tmp_path):
        trajectory_path = tmp_path / "out.tum"
        config = ExternalToolConfig(
            command=_write_tum_command(trajectory_path),
            trajectory_path=trajectory_path,
            tool_name="demo_slam",
        )
        trajectory = ExternalToolBackend().run(_empty_sequence(), config=config)

        assert trajectory.method == "external"
        assert len(trajectory.timestamps) == 3
        np.testing.assert_allclose(trajectory.positions[:, 0], [0.0, 1.0, 2.0])
        assert config.execution is not None
        assert config.execution.returncode == 0

    def test_missing_output_file_raises(self, tmp_path):
        config = ExternalToolConfig(
            command=f"{_PY} -c \"print('no output written')\"",
            trajectory_path=tmp_path / "never_written.tum",
            tool_name="silent",
        )
        with pytest.raises(ExternalToolError, match="did not write"):
            ExternalToolBackend().run(_empty_sequence(), config=config)

    def test_requires_trajectory_path(self):
        with pytest.raises(ValueError, match="trajectory_path"):
            ExternalToolBackend().run(_empty_sequence(), config=ExternalToolConfig(command="true"))


def _cli(argv: list[str]) -> None:
    from nav_benchmark.run import main

    with mock.patch.object(sys, "argv", ["nav_benchmark.run", *argv]):
        main()


class TestExternalToolCli:
    def test_run_with_external_command_records_execution_in_manifest(self, tmp_path):
        trajectory_path = tmp_path / "tool_out.tum"
        output_root = tmp_path / "runs"
        _cli(
            [
                "run",
                "--method",
                "external",
                "--dataset",
                "synthetic",
                "--sequence",
                "ext_tool",
                "--external-trajectory",
                str(trajectory_path),
                "--external-command",
                _write_tum_command(trajectory_path),
                "--external-tool-name",
                "demo_slam",
                "--external-version-command",
                f"{_PY} --version",
                "--output-root",
                str(output_root),
            ]
        )

        run_dir = next(output_root.glob("*_external_ext_tool"))
        assert (run_dir / "estimated_trajectory.csv").exists()

        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "success"
        execution = manifest["config"]["execution"]
        assert execution["tool_name"] == "demo_slam"
        assert execution["returncode"] == 0
        assert execution["tool_version"].startswith("Python")

    def test_failed_external_command_writes_failure_manifest_and_notes(self, tmp_path):
        output_root = tmp_path / "runs"
        command = f"{_PY} -c \"import sys; sys.stderr.write('sensor init failed\\n'); sys.exit(2)\""
        with pytest.raises(ExternalToolError):
            _cli(
                [
                    "run",
                    "--method",
                    "external",
                    "--dataset",
                    "synthetic",
                    "--sequence",
                    "ext_fail",
                    "--external-trajectory",
                    str(tmp_path / "never.tum"),
                    "--external-command",
                    command,
                    "--external-tool-name",
                    "broken_slam",
                    "--output-root",
                    str(output_root),
                ]
            )

        run_dir = next(output_root.glob("*_external_ext_fail"))
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "failed"
        assert "exit code 2" in manifest["error_message"]
        assert manifest["external_execution"]["returncode"] == 2
        assert "sensor init failed" in manifest["external_execution"]["stderr_tail"]

        notes = (run_dir / "failure_notes.md").read_text(encoding="utf-8")
        assert "Run Failed" in notes
        assert "broken_slam" in notes or "exit code 2" in notes

        log_text = (run_dir / "run.log").read_text(encoding="utf-8")
        assert "[FAILED]" in log_text


def _full_sequence() -> MvsecSequence:
    events = np.zeros(4, dtype=EVENT_DTYPE)
    events["t"] = [0.0, 0.1, 0.2, 0.3]
    events["x"] = [1, 2, 3, 4]
    events["y"] = [4, 3, 2, 1]
    events["p"] = [1, -1, 1, -1]

    imu = np.zeros(3, dtype=IMU_DTYPE)
    imu["t"] = [0.0, 0.5, 1.0]
    imu["ax"] = [0.1, 0.2, 0.3]
    imu["az"] = [9.81, 9.81, 9.81]

    gt = np.zeros(2, dtype=POSE_DTYPE)
    gt["t"] = [0.0, 1.0]
    gt["x"] = [0.0, 1.0]
    gt["qw"] = [1.0, 1.0]

    images = np.zeros((2, 8, 8), dtype=np.uint8)
    images[0, 2, 2] = 255
    images[1, 3, 3] = 255

    return MvsecSequence(
        metadata=SequenceMetadata(source_path="unit", sequence_name="convert_unit"),
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(),
        events=events,
        imu=imu,
        gt_poses=gt,
        images=images,
        image_timestamps=np.array([0.0, 0.5]),
    )


class TestDatasetConversion:
    def test_exports_all_streams_with_manifest(self, tmp_path):
        manifest = export_sequence_streams(_full_sequence(), tmp_path)

        assert set(manifest["streams"]) == {"events", "imu", "ground_truth", "images"}
        assert manifest["streams"]["events"]["count"] == 4
        assert (tmp_path / "events.csv").exists()
        assert (tmp_path / "imu.csv").exists()
        assert (tmp_path / "ground_truth.csv").exists()
        assert (tmp_path / "images" / "frame_000000.png").exists()
        assert (tmp_path / "image_timestamps.csv").exists()

        saved_manifest = json.loads((tmp_path / "conversion_manifest.json").read_text(encoding="utf-8"))
        assert saved_manifest["sequence_name"] == "convert_unit"

        events_lines = (tmp_path / "events.csv").read_text(encoding="utf-8").strip().splitlines()
        assert events_lines[0] == "t,x,y,p"
        assert events_lines[1].startswith("0.000000000,1,4,1")

    def test_deterministic_output(self, tmp_path):
        first_dir = tmp_path / "a"
        second_dir = tmp_path / "b"
        export_sequence_streams(_full_sequence(), first_dir)
        export_sequence_streams(_full_sequence(), second_dir)
        for name in ("events.csv", "imu.csv", "ground_truth.csv"):
            assert (first_dir / name).read_text(encoding="utf-8") == (second_dir / name).read_text(encoding="utf-8")

    def test_omits_missing_streams(self, tmp_path):
        manifest = export_sequence_streams(_empty_sequence(), tmp_path)
        assert manifest["streams"] == {}
        assert not (tmp_path / "events.csv").exists()

    def test_convert_cli_synthetic(self, tmp_path):
        output_dir = tmp_path / "converted"
        _cli(
            [
                "convert",
                "--dataset",
                "synthetic",
                "--sequence",
                "conv_demo",
                "--output-dir",
                str(output_dir),
            ]
        )
        manifest = json.loads((output_dir / "conversion_manifest.json").read_text(encoding="utf-8"))
        assert "imu" in manifest["streams"]
        assert (output_dir / "imu.csv").exists()
