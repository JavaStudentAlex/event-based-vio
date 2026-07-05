"""Wrapper backends for trajectories produced by external SLAM/VIO tools.

Two integration paths for strong external baselines such as UltimateSLAM or
ESVO:

- ``ExternalTrajectoryBackend``: the tool already ran (offline, container,
  another machine); feed its exported trajectory (TUM or project CSV) through
  the project export/evaluation/validation contract.
- ``ExternalToolBackend``: run the external tool as a subprocess with a
  timeout, capture its exit status and stderr for diagnostics, then normalize
  the trajectory file it wrote exactly like the offline path.

See ``docs/baselines/external.md`` for tool setup and adapter usage.
"""

import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.export import read_tum_trajectory
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

_OUTPUT_TAIL_LINES = 20


@dataclass
class ExternalTrajectoryConfig:
    """Configuration for normalizing an externally produced trajectory."""

    trajectory_path: str | Path = ""
    format: str = "auto"  # "tum", "csv", or "auto" (by file extension)
    default_confidence: float = 0.8
    gap_degraded_sec: float = 0.5


def _resolve_format(path: Path, declared: str) -> str:
    if declared != "auto":
        return declared
    return "csv" if path.suffix.lower() == ".csv" else "tum"


def _gap_health(timestamps: np.ndarray, gap_degraded_sec: float) -> np.ndarray:
    """Mark samples that follow a timestamp gap larger than the threshold as DEGRADED."""
    health = np.array([PoseHealth.OK.value] * len(timestamps), dtype=object)
    if len(timestamps) > 1:
        gaps = np.diff(timestamps)
        health[1:][gaps > gap_degraded_sec] = PoseHealth.DEGRADED.value
    return health


def _from_tum(path: Path, config: ExternalTrajectoryConfig) -> Trajectory:
    trajectory = read_tum_trajectory(path, method="external")
    count = len(trajectory.timestamps)
    return Trajectory(
        timestamps=trajectory.timestamps,
        method="external",
        positions=trajectory.positions,
        orientations=trajectory.orientations,
        confidence=np.full(count, config.default_confidence),
        health=_gap_health(trajectory.timestamps, config.gap_degraded_sec),
        latency_ms=np.zeros(count),
    )


def _from_project_csv(path: Path) -> Trajectory:
    from nav_benchmark.evaluation.metrics import read_project_csv

    loaded = read_project_csv(path)
    return Trajectory(
        timestamps=loaded.timestamps,
        method="external",
        positions=loaded.positions,
        orientations=loaded.orientations,
        velocities=loaded.velocities,
        confidence=loaded.confidence,
        health=loaded.health,
        latency_ms=loaded.latency_ms,
    )


class ExternalTrajectoryBackend(BaseOdometryBackend):
    """Normalize an external tool's trajectory into the project backend contract."""

    method = "external"
    required_streams = ()

    def run(self, sequence: MvsecSequence, *, config: ExternalTrajectoryConfig | None = None) -> Trajectory:
        if config is None or not str(config.trajectory_path):
            raise ValueError("ExternalTrajectoryBackend requires a config with trajectory_path")

        path = Path(config.trajectory_path)
        if not path.exists():
            raise FileNotFoundError(f"External trajectory file not found: {path}")

        fmt = _resolve_format(path, config.format)
        if fmt == "csv":
            return _from_project_csv(path)
        if fmt == "tum":
            return _from_tum(path, config)
        raise ValueError(f"Unsupported external trajectory format: {fmt!r}")


@dataclass
class ExternalToolExecution:
    """Reproducibility record of one external tool invocation."""

    command: str
    tool_name: str
    returncode: int | None = None
    duration_sec: float | None = None
    timed_out: bool = False
    tool_version: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


class ExternalToolError(RuntimeError):
    """External tool execution failed; carries the execution record for diagnostics."""

    def __init__(self, message: str, execution: ExternalToolExecution):
        super().__init__(message)
        self.execution = execution


@dataclass
class ExternalToolConfig:
    """Configuration for running an external SLAM/VIO tool via subprocess.

    ``trajectory_path`` is the file the tool is expected to write; after the
    subprocess exits successfully it is normalized exactly like an offline
    external trajectory. ``execution`` is filled in by the backend after the
    run so the manifest records tool version, exit status, and timing.
    """

    command: str = ""
    trajectory_path: str | Path = ""
    format: str = "auto"
    workdir: str | Path | None = None
    timeout_sec: float = 3600.0
    tool_name: str = "external"
    version_command: str | None = None
    default_confidence: float = 0.8
    gap_degraded_sec: float = 0.5
    execution: ExternalToolExecution | None = field(default=None, repr=False)


def _output_tail(text: str | None) -> str:
    if not text:
        return ""
    lines = text.strip().splitlines()
    return "\n".join(lines[-_OUTPUT_TAIL_LINES:])


def _workdir_str(config: ExternalToolConfig) -> str | None:
    return str(config.workdir) if config.workdir else None


def _probe_tool_version(config: ExternalToolConfig) -> str | None:
    if not config.version_command:
        return None
    try:
        probe = subprocess.run(
            shlex.split(config.version_command),
            cwd=_workdir_str(config),
            capture_output=True,
            text=True,
            timeout=60.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (probe.stdout or probe.stderr).strip()
    return output.splitlines()[0] if output else None


def _record_timeout(execution: ExternalToolExecution, error: subprocess.TimeoutExpired) -> None:
    execution.timed_out = True
    execution.stdout_tail = _output_tail(error.stdout if isinstance(error.stdout, str) else None)
    execution.stderr_tail = _output_tail(error.stderr if isinstance(error.stderr, str) else None)


def _nonzero_exit_message(config: ExternalToolConfig, execution: ExternalToolExecution, returncode: int) -> str:
    stderr_tail = execution.stderr_tail or "(empty)"
    return f"External tool {config.tool_name!r} failed with exit code {returncode}. stderr tail:\n{stderr_tail}"


def run_external_tool(config: ExternalToolConfig) -> ExternalToolExecution:
    """Run the configured external tool, returning its execution record.

    Raises :class:`ExternalToolError` on a missing binary, non-zero exit, or
    timeout; the raised error carries the execution record so callers can
    still write the manifest and failure notes.
    """
    if not config.command.strip():
        raise ValueError("ExternalToolConfig.command must not be empty")

    execution = ExternalToolExecution(
        command=config.command,
        tool_name=config.tool_name,
        tool_version=_probe_tool_version(config),
    )
    argv = shlex.split(config.command)
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=_workdir_str(config),
            capture_output=True,
            text=True,
            timeout=config.timeout_sec,
        )
    except FileNotFoundError as e:
        execution.duration_sec = time.perf_counter() - start
        raise ExternalToolError(
            f"External tool binary not found: {argv[0]!r}. Check the setup instructions in docs/baselines/external.md",
            execution,
        ) from e
    except subprocess.TimeoutExpired as e:
        execution.duration_sec = time.perf_counter() - start
        _record_timeout(execution, e)
        raise ExternalToolError(
            f"External tool {config.tool_name!r} timed out after {config.timeout_sec:.0f}s",
            execution,
        ) from e

    execution.duration_sec = time.perf_counter() - start
    execution.returncode = completed.returncode
    execution.stdout_tail = _output_tail(completed.stdout)
    execution.stderr_tail = _output_tail(completed.stderr)

    if completed.returncode != 0:
        raise ExternalToolError(_nonzero_exit_message(config, execution, completed.returncode), execution)
    return execution


class ExternalToolBackend(BaseOdometryBackend):
    """Run an external SLAM/VIO tool via subprocess and normalize its trajectory."""

    method = "external"
    required_streams = ()

    def run(self, sequence: MvsecSequence, *, config: ExternalToolConfig | None = None) -> Trajectory:
        if config is None or not str(config.trajectory_path):
            raise ValueError("ExternalToolBackend requires a config with trajectory_path")

        config.execution = run_external_tool(config)

        trajectory_path = Path(config.trajectory_path)
        if not trajectory_path.exists():
            raise ExternalToolError(
                f"External tool {config.tool_name!r} exited successfully but did not write "
                f"the expected trajectory file: {trajectory_path}",
                config.execution,
            )

        loader_config = ExternalTrajectoryConfig(
            trajectory_path=trajectory_path,
            format=config.format,
            default_confidence=config.default_confidence,
            gap_degraded_sec=config.gap_degraded_sec,
        )
        return ExternalTrajectoryBackend().run(sequence, config=loader_config)
