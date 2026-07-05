import argparse
import csv
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

import numpy as np

from nav_benchmark.baselines.event_imu import EventImuBackend, EventImuConfig
from nav_benchmark.baselines.external import (
    ExternalToolBackend,
    ExternalToolConfig,
    ExternalToolError,
    ExternalTrajectoryBackend,
    ExternalTrajectoryConfig,
)
from nav_benchmark.baselines.image_imu import ImageImuBackend, ImageImuConfig
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.baselines.multimodal_vio import MultimodalVioBackend, MultimodalVioConfig
from nav_benchmark.baselines.visual import EventVoBackend, FeatureVoConfig, RgbVoBackend
from nav_benchmark.datasets.mvsec import (
    IMU_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
    load_mvsec_sequence,
)
from nav_benchmark.datasets.synthetic import load_synthetic_sequence
from nav_benchmark.ensemble.confidence_weighted import EnsembleConfig, fuse_trajectories, write_weight_log_csv
from nav_benchmark.ensemble.fusion import (
    EkfFusionConfig,
    WinnerTakesHealthyConfig,
    run_weighted_ekf_fusion,
    run_winner_takes_healthy,
    sample_backend_health,
    write_update_log_csv,
)
from nav_benchmark.evaluation.harness import (
    evaluate_run_directory,
    load_ground_truth_trajectory,
    resolve_ground_truth_path,
    write_evaluation_artifacts,
)
from nav_benchmark.evaluation.metrics import (
    EvalConfig,
    make_json_serializable,
)
from nav_benchmark.evaluation.plots import write_backend_status_timeline_plot, write_ensemble_weight_plot
from nav_benchmark.events import (
    EventStreamDiagnostics,
    diagnose_event_stream,
    ensure_event_frames,
    infer_sequence_resolution,
)
from nav_benchmark.trajectory.export import export_project_csv, export_tum
from nav_benchmark.trajectory.models import ExportMetadata, Trajectory
from nav_benchmark.validation import validate_run_directory


def get_code_version() -> str:
    return _installed_code_version() or _pyproject_code_version() or "0.1.0"


def _installed_code_version() -> str | None:
    try:
        import importlib.metadata

        return importlib.metadata.version("event-based-vio")
    except Exception:
        return None


def _pyproject_code_version() -> str | None:
    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path) as f:
                for line in f:
                    if line.strip().startswith("version ="):
                        return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


def process_resource_usage() -> dict[str, float]:
    """CPU time and peak memory of this process, for reproducibility metadata."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "cpu_user_sec": float(usage.ru_utime),
        "cpu_system_sec": float(usage.ru_stime),
        # ru_maxrss is kilobytes on Linux.
        "max_rss_mb": float(usage.ru_maxrss) / 1024.0,
    }


def _health_intervals(trajectory: Trajectory) -> list[tuple[str, float, float]]:
    intervals = []
    if trajectory.health is not None and len(trajectory.health) > 0:
        current_state = str(trajectory.health[0])
        start_time = float(trajectory.timestamps[0])

        for i in range(1, len(trajectory.health)):
            h = str(trajectory.health[i])
            if h != current_state:
                end_time = float(trajectory.timestamps[i - 1])
                intervals.append((current_state, start_time, end_time))
                current_state = h
                start_time = float(trajectory.timestamps[i])
        intervals.append((current_state, start_time, float(trajectory.timestamps[-1])))
    return intervals


def _intervals_text(intervals: list[tuple[str, float, float]]) -> str:
    degraded_lost_intervals = [item for item in intervals if item[0] in ("DEGRADED", "LOST")]
    if not degraded_lost_intervals:
        return "No degraded or lost intervals were detected."
    lines = []
    for state, t_start, t_end in degraded_lost_intervals:
        duration = t_end - t_start
        lines.append(f"- **{state}**: {t_start:.4f}s to {t_end:.4f}s (duration: {duration:.4f}s)")
    return "\n".join(lines)


def _failure_guidance_text(method: str) -> str:
    if method == "imu_only":
        return (
            "IMU-only propagation accumulates integration drift rapidly without correction. "
            "It is highly recommended to fuse visual or event streams (e.g. image_imu, event_imu) "
            "to bound errors and prevent tracking loss."
        )
    return "Monitor tracking health and investigate calibration or sync anomalies."


def generate_failure_notes(trajectory: Trajectory, metadata: ExportMetadata) -> str:
    ok_count = metadata.health_counts.get("OK", 0)
    degraded_count = metadata.health_counts.get("DEGRADED", 0)
    lost_count = metadata.health_counts.get("LOST", 0)
    invalid_count = metadata.health_counts.get("INVALID", 0)
    intervals_text = _intervals_text(_health_intervals(trajectory))
    guidance_text = _failure_guidance_text(trajectory.method)

    return f"""# Run Failure Notes

## Health Summary
- **OK**: {ok_count}
- **DEGRADED**: {degraded_count}
- **LOST**: {lost_count}
- **INVALID**: {invalid_count}

## Detected Degraded/Lost Intervals
{intervals_text}

## Guidance
{guidance_text}
"""


def _event_window_sec(args) -> float:
    window_ms = float(getattr(args, "event_window_ms", 50.0))
    if window_ms <= 0.0:
        raise ValueError("--event-window-ms must be positive")
    return window_ms / 1000.0


def _prepare_event_streams(sequence: MvsecSequence, args, log_message) -> MvsecSequence:
    if ensure_event_frames(sequence, window_sec=_event_window_sec(args)):
        frame_count = len(sequence.event_frames) if sequence.event_frames is not None else 0
        log_message(
            f"Built {frame_count} event frames from raw events (window {getattr(args, 'event_window_ms', 50.0)} ms)"
        )
    return sequence


def sequence_event_diagnostics(sequence: MvsecSequence, *, window_sec: float) -> EventStreamDiagnostics | None:
    """Diagnose raw event stream health, or None when the sequence carries no events."""
    if sequence.events is None or len(sequence.events) == 0:
        return None
    height, width = infer_sequence_resolution(sequence)
    return diagnose_event_stream(sequence.events, height, width, window_sec=window_sec)


def load_dataset_sequence(args, log_message) -> MvsecSequence:
    if args.dataset == "synthetic":
        if args.input:
            log_message(f"Loading generated synthetic sequence from {args.input}...")
            sequence = load_synthetic_sequence(args.input, sequence_name=args.sequence)
            return _prepare_event_streams(sequence, args, log_message)

        log_message("Generating synthetic sequence data...")
        N = 100
        imu_data = np.empty(N, dtype=IMU_DTYPE)
        imu_data["t"] = np.linspace(0.0, 0.99, N)
        imu_data["ax"] = np.zeros(N)
        imu_data["ay"] = np.zeros(N)
        imu_data["az"] = np.ones(N) * 9.81  # matches standard gravity config
        imu_data["gx"] = np.zeros(N)
        imu_data["gy"] = np.zeros(N)
        imu_data["gz"] = np.zeros(N)

        return MvsecSequence(
            metadata=SequenceMetadata(
                source_path="synthetic",
                sequence_name=args.sequence,
            ),
            diagnostics=LoadDiagnostics(),
            calibration=Calibration(),
            imu=imu_data,
        )
    else:
        log_message(f"Loading MVSEC sequence from {args.input}...")
        sequence = load_mvsec_sequence(args.input)
        return _prepare_event_streams(sequence, args, log_message)


def _initial_velocity_from_ground_truth(sequence: MvsecSequence) -> np.ndarray:
    if sequence.gt_poses is None or len(sequence.gt_poses) < 2:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)

    gt = sequence.gt_poses
    dt = float(gt["t"][1] - gt["t"][0])
    if dt <= 0.0:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)

    first = np.array([gt["x"][0], gt["y"][0], gt["z"][0]], dtype=np.float64)
    second = np.array([gt["x"][1], gt["y"][1], gt["z"][1]], dtype=np.float64)
    return (second - first) / dt


def _imu_only_config_for_sequence(args, sequence: MvsecSequence) -> ImuOnlyConfig:
    config = ImuOnlyConfig()

    gravity = np.array([0.0, 0.0, 9.81], dtype=np.float64)
    if args.dataset == "synthetic" and args.input:
        # Generated synthetic IMU reports accelerometer rest as -gravity.
        gravity = np.array([0.0, 0.0, -9.81], dtype=np.float64)

    initial_position = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    initial_orientation = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    initial_velocity = np.array([0.0, 0.0, 0.0], dtype=np.float64)

    if sequence.gt_poses is not None and len(sequence.gt_poses) > 0:
        gt = sequence.gt_poses
        initial_position = np.array([gt["x"][0], gt["y"][0], gt["z"][0]], dtype=np.float64)
        initial_orientation = np.array([gt["qx"][0], gt["qy"][0], gt["qz"][0], gt["qw"][0]], dtype=np.float64)
        initial_velocity = _initial_velocity_from_ground_truth(sequence)

    config.gravity = gravity
    config.initial_position = initial_position
    config.initial_orientation = initial_orientation
    config.initial_velocity = initial_velocity
    return config


def _debug_dir(run_dir: Path | None, method: str) -> Path | None:
    if run_dir is None:
        return None
    return run_dir / "diagnostics" / method


def _rgb_vo_config(run_dir: Path | None) -> FeatureVoConfig:
    return FeatureVoConfig(scale_bias=1.01, debug_match_dir=_debug_dir(run_dir, "rgb_vo_matches"))


def _event_vo_config(run_dir: Path | None) -> FeatureVoConfig:
    return FeatureVoConfig(scale_bias=0.98, debug_match_dir=_debug_dir(run_dir, "event_vo_matches"))


def _run_backend(backend, sequence: MvsecSequence, config):
    result = backend.run_result(sequence, config=config)
    return result.trajectory, config


def _run_imu_only(args, sequence: MvsecSequence, run_dir: Path | None):
    return _run_backend(ImuOnlyBackend(), sequence, _imu_only_config_for_sequence(args, sequence))


def _run_rgb_vo(args, sequence: MvsecSequence, run_dir: Path | None):
    return _run_backend(RgbVoBackend(), sequence, _rgb_vo_config(run_dir))


def _run_event_vo(args, sequence: MvsecSequence, run_dir: Path | None):
    return _run_backend(EventVoBackend(), sequence, _event_vo_config(run_dir))


def _run_event_imu(args, sequence: MvsecSequence, run_dir: Path | None):
    config = EventImuConfig(
        imu_config=_imu_only_config_for_sequence(args, sequence),
        event_window_sec=_event_window_sec(args),
    )
    result = EventImuBackend().run_result(sequence, config=config)
    config.run_diagnostics = result.diagnostics
    return result.trajectory, config


def _run_image_imu(args, sequence: MvsecSequence, run_dir: Path | None):
    config = ImageImuConfig(
        imu_config=_imu_only_config_for_sequence(args, sequence),
        rgb_vo_config=_rgb_vo_config(run_dir),
    )
    return _run_backend(ImageImuBackend(), sequence, config)


def _run_multimodal_vio(args, sequence: MvsecSequence, run_dir: Path | None):
    config = MultimodalVioConfig(
        imu_config=_imu_only_config_for_sequence(args, sequence),
        rgb_vo_config=_rgb_vo_config(run_dir),
        event_vo_config=_event_vo_config(run_dir),
    )
    return _run_backend(MultimodalVioBackend(), sequence, config)


def _run_external(args, sequence: MvsecSequence, run_dir: Path | None):
    command = getattr(args, "external_command", None)
    if command:
        tool_config = ExternalToolConfig(
            command=command,
            trajectory_path=getattr(args, "external_trajectory", "") or "",
            format=getattr(args, "external_format", "auto"),
            workdir=getattr(args, "external_workdir", None),
            timeout_sec=getattr(args, "external_timeout_sec", 3600.0),
            tool_name=getattr(args, "external_tool_name", "external"),
            version_command=getattr(args, "external_version_command", None),
        )
        return _run_backend(ExternalToolBackend(), sequence, tool_config)
    config = ExternalTrajectoryConfig(
        trajectory_path=getattr(args, "external_trajectory", "") or "",
        format=getattr(args, "external_format", "auto"),
    )
    return _run_backend(ExternalTrajectoryBackend(), sequence, config)


def _ensemble_baselines(args, sequence: MvsecSequence, run_dir: Path | None, imu_config: ImuOnlyConfig):
    baseline_trajectories = {}
    baseline_trajectories["imu_only"] = ImuOnlyBackend().run(sequence, config=imu_config)
    baseline_trajectories["rgb_vo"] = RgbVoBackend().run(sequence, config=_rgb_vo_config(run_dir))
    baseline_trajectories["event_vo"] = EventVoBackend().run(sequence, config=_event_vo_config(run_dir))

    event_imu_config = EventImuConfig(imu_config=imu_config, event_window_sec=_event_window_sec(args))
    image_imu_config = ImageImuConfig(imu_config=imu_config, rgb_vo_config=_rgb_vo_config(run_dir))
    multimodal_vio_config = MultimodalVioConfig(
        imu_config=imu_config,
        rgb_vo_config=_rgb_vo_config(run_dir),
        event_vo_config=_event_vo_config(run_dir),
    )
    baseline_trajectories["event_imu"] = EventImuBackend().run(sequence, config=event_imu_config)
    baseline_trajectories["image_imu"] = ImageImuBackend().run(sequence, config=image_imu_config)
    baseline_trajectories["multimodal_vio"] = MultimodalVioBackend().run(sequence, config=multimodal_vio_config)

    baseline_configs = {
        "imu_config": imu_config,
        "event_imu_config": event_imu_config,
        "image_imu_config": image_imu_config,
        "multimodal_vio_config": multimodal_vio_config,
    }
    return baseline_trajectories, baseline_configs


def _require_sequence_imu(sequence: MvsecSequence) -> np.ndarray:
    if sequence.imu is None or len(sequence.imu) == 0:
        raise ValueError("Weighted EKF ensemble fusion requires IMU data in the sequence")
    return sequence.imu


def _run_ekf_ensemble(sequence: MvsecSequence, baselines: dict, imu_config: ImuOnlyConfig, run_dir: Path | None):
    from nav_benchmark.ensemble.ekf import EkfConfig

    imu = _require_sequence_imu(sequence)
    measurements = {method: trajectory for method, trajectory in baselines.items() if method != "imu_only"}
    fusion_config = EkfFusionConfig(ekf=EkfConfig(gravity=imu_config.gravity))
    trajectory, records = run_weighted_ekf_fusion(
        imu,
        measurements,
        config=fusion_config,
        initial_position=imu_config.initial_position,
        initial_velocity=imu_config.initial_velocity,
        initial_orientation_xyzw=imu_config.initial_orientation,
    )
    if run_dir is not None:
        write_update_log_csv(records, run_dir / "ensemble_updates.csv")
        write_update_log_csv(records, run_dir / "rejected_updates.csv", only_rejected=True)
    return trajectory, fusion_config


def _write_status_timeline(args, baselines: dict, trajectory: Trajectory, run_dir: Path | None) -> None:
    if run_dir is None:
        return
    try:
        health_by_method = sample_backend_health(baselines, trajectory.timestamps)
        write_backend_status_timeline_plot(
            health_by_method, trajectory.timestamps, run_dir / "backend_status_timeline", sequence=args.sequence
        )
    except Exception as plot_err:
        print(f"Warning: failed to write backend status timeline: {plot_err}", file=sys.stderr)


def _fuse_ensemble(args, sequence: MvsecSequence, baselines: dict, imu_config: ImuOnlyConfig, run_dir: Path | None):
    fusion_mode = getattr(args, "fusion", "confidence_weighted")
    if fusion_mode == "weighted_ekf":
        return _run_ekf_ensemble(sequence, baselines, imu_config, run_dir)
    if fusion_mode == "winner_takes_healthy":
        wth_config = WinnerTakesHealthyConfig()
        return run_winner_takes_healthy(baselines, config=wth_config), wth_config
    return fuse_trajectories(baselines, config=EnsembleConfig()), EnsembleConfig()


def _run_ensemble(args, sequence: MvsecSequence, run_dir: Path | None):
    imu_config = _imu_only_config_for_sequence(args, sequence)
    baselines, baseline_configs = _ensemble_baselines(args, sequence, run_dir, imu_config)
    trajectory, fusion_config = _fuse_ensemble(args, sequence, baselines, imu_config, run_dir)
    _write_status_timeline(args, baselines, trajectory, run_dir)

    return trajectory, {
        "fusion_mode": getattr(args, "fusion", "confidence_weighted"),
        "ensemble": fusion_config,
        "input_methods": sorted(baselines),
        **baseline_configs,
    }


_ESTIMATOR_RUNNERS = {
    "imu_only": _run_imu_only,
    "rgb_vo": _run_rgb_vo,
    "event_vo": _run_event_vo,
    "event_imu": _run_event_imu,
    "image_imu": _run_image_imu,
    "multimodal_vio": _run_multimodal_vio,
    "ensemble": _run_ensemble,
    "external": _run_external,
}


def run_estimator(args, sequence, run_dir: Path | None = None):
    runner = _ESTIMATOR_RUNNERS.get(args.method)
    if runner is None:
        raise NotImplementedError(f"Method {args.method} is not implemented")
    return runner(args, sequence, run_dir)


def write_run_manifest(
    args, config, metadata, run_dir, *, event_diagnostics: EventStreamDiagnostics | None = None
) -> dict:
    from nav_benchmark.trajectory.models import PoseHealth

    health_counts = {h.value: metadata.health_counts.get(h.value, 0) for h in PoseHealth}
    serialized_config = make_json_serializable(config)

    run_manifest = {
        "method": args.method,
        "dataset": args.dataset,
        "sequence": args.sequence,
        "input": getattr(args, "input", None),
        "config": serialized_config,
        "timestamp_policy": metadata.timestamp_unit,
        "gravity": config.gravity.tolist() if hasattr(config, "gravity") else [0.0, 0.0, 9.81],
        "frames": {
            "source": metadata.source_frame,
            "target": metadata.target_frame,
        },
        "units": {
            "position": metadata.position_units,
            "orientation": metadata.orientation_format,
        },
        "alignment": {
            "policy": metadata.association_policy,
            "tolerance_sec": metadata.association_tolerance_sec,
        },
        "code_version": get_code_version(),
        "status": "success",
        "health_counts": health_counts,
    }
    if event_diagnostics is not None:
        run_manifest["event_diagnostics"] = make_json_serializable(event_diagnostics)
    run_manifest["resource_usage"] = process_resource_usage()

    manifest_path = run_dir / "run_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(run_manifest, f, indent=4)
    return run_manifest


def _load_run_manifest(run_dir: Path) -> dict[str, Any] | None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _method_filter_matches(manifest: dict[str, Any], method: str | None) -> bool:
    return method is None or manifest.get("method") == method


def _sequence_filter_matches(manifest: dict[str, Any], sequence: str | None) -> bool:
    return sequence is None or manifest.get("sequence") == sequence


def _manifest_matches_filters(
    manifest: dict[str, Any] | None, method: str | None = None, sequence: str | None = None
) -> bool:
    if method is None and sequence is None:
        return True
    if manifest is None:
        return False
    return _method_filter_matches(manifest, method) and _sequence_filter_matches(manifest, sequence)


def _is_run_dir_candidate(path: Path, method: str | None = None, sequence: str | None = None) -> bool:
    if not path.is_dir():
        return False
    if not (path / "estimated_trajectory.csv").exists():
        return False
    return _manifest_matches_filters(_load_run_manifest(path), method=method, sequence=sequence)


def discover_latest_run_dir(output_root: Path, method: str | None = None, sequence: str | None = None) -> Path | None:
    if not output_root.exists():
        return None

    candidates = [path for path in output_root.iterdir() if _is_run_dir_candidate(path, method, sequence)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p / "estimated_trajectory.csv").stat().st_mtime, reverse=True)
    return candidates[0]


def load_ground_truth(path: Path) -> Trajectory:
    return load_ground_truth_trajectory(path)


def write_failed_evaluation_artifacts(run_dir: Path, reason: str, config: EvalConfig) -> None:
    failed_result: dict[str, Any] = {
        "status": "failed",
        "reason": reason,
        "error_message": reason,
        "config": {
            "association_tolerance_sec": config.association_tolerance_sec,
            "alignment_policy": config.alignment_policy,
            "correct_scale": config.correct_scale,
            "time_offset_search": config.time_offset_search,
            "outlier_rejection": config.outlier_rejection,
            "rpe_delta_m": config.rpe_delta_m,
            "drift_bin_width_m": config.drift_bin_width_m,
        },
        "diagnostics": None,
        "coverage": None,
        "runtime": None,
        "failures": None,
        "alignment": None,
        "metrics": None,
        "drift_bins": [],
        "error_vs_time": [],
        "error_vs_distance": [],
        "aligned_estimate": None,
        "aligned_ground_truth": None,
    }
    with open(run_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(failed_result, f, indent=2)

    with open(run_dir / "ground_truth_aligned.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "method",
                "x",
                "y",
                "z",
                "qx",
                "qy",
                "qz",
                "qw",
                "vx",
                "vy",
                "vz",
                "confidence",
                "health",
                "latency_ms",
            ]
        )

    with open(run_dir / "error_vs_time.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "est_x",
                "est_y",
                "est_z",
                "gt_aligned_x",
                "gt_aligned_y",
                "gt_aligned_z",
                "error_x",
                "error_y",
                "error_z",
                "error_magnitude",
                "health",
                "association_residual",
            ]
        )

    with open(run_dir / "error_vs_distance.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["cumulative_distance", "error_magnitude", "health", "association_residual", "bin_start", "bin_end"]
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visual-Inertial Navigation Benchmark Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand 'run'
    run_parser = subparsers.add_parser("run", help="Run baseline or ensemble estimation on dataset")
    run_parser.add_argument(
        "--method",
        required=True,
        choices=["imu_only", "rgb_vo", "event_vo", "event_imu", "image_imu", "multimodal_vio", "ensemble", "external"],
        help="Estimation method to run",
    )
    run_parser.add_argument(
        "--dataset",
        required=True,
        choices=["synthetic", "mvsec"],
        help="Dataset type",
    )
    run_parser.add_argument(
        "--sequence",
        required=True,
        help="Name of the sequence to process",
    )
    run_parser.add_argument(
        "--input",
        help="Path to input MVSEC dataset HDF5 file (required for mvsec dataset)",
    )
    run_parser.add_argument(
        "--output-root",
        default="runs",
        help="Root directory where run output folders are created",
    )
    run_parser.add_argument(
        "--resume",
        action="store_true",
        help="If the target run directory exists, append a suffix like -r{N} to avoid error",
    )
    run_parser.add_argument(
        "--event-window-ms",
        type=float,
        default=50.0,
        help="Window length in milliseconds for event frames built from raw events and event diagnostics",
    )
    run_parser.add_argument(
        "--fusion",
        choices=["confidence_weighted", "weighted_ekf", "winner_takes_healthy"],
        default="confidence_weighted",
        help="Fusion mode used when --method is 'ensemble'",
    )
    run_parser.add_argument(
        "--external-trajectory",
        help="Path to an externally produced trajectory (TUM or project CSV); required for --method external",
    )
    run_parser.add_argument(
        "--external-format",
        choices=["auto", "tum", "csv"],
        default="auto",
        help="Format of the external trajectory file",
    )
    run_parser.add_argument(
        "--external-command",
        help=(
            "Command that runs the external tool (executed via subprocess); the tool must write "
            "the trajectory file given by --external-trajectory"
        ),
    )
    run_parser.add_argument(
        "--external-workdir",
        help="Working directory for --external-command",
    )
    run_parser.add_argument(
        "--external-timeout-sec",
        type=float,
        default=3600.0,
        help="Timeout in seconds for --external-command",
    )
    run_parser.add_argument(
        "--external-tool-name",
        default="external",
        help="Human-readable external tool name recorded in the run manifest",
    )
    run_parser.add_argument(
        "--external-version-command",
        help="Command whose first output line is recorded as the external tool version",
    )
    run_parser.add_argument(
        "--evaluate",
        action="store_true",
        help="After a successful run, evaluate against ground truth and write evaluation artifacts",
    )
    run_parser.add_argument(
        "--ground-truth",
        help="Ground truth trajectory path used with --evaluate (defaults to the run input's ground truth)",
    )

    # Subcommand 'eval'
    eval_parser = subparsers.add_parser("eval", help="Evaluate a completed run trajectory against ground truth")
    eval_parser.add_argument(
        "--run-dir",
        help="Path to the run directory to evaluate (required unless --latest is set)",
    )
    eval_parser.add_argument(
        "--latest",
        action="store_true",
        help="Automatically find and evaluate the latest run directory in --output-root",
    )
    eval_parser.add_argument(
        "--ground-truth",
        help="Path to the ground truth trajectory file (CSV or MVSEC HDF5 file)",
    )
    eval_parser.add_argument(
        "--output-root",
        default="runs",
        help="Root directory where run folders are stored (used with --latest)",
    )
    eval_parser.add_argument(
        "--method",
        help="Filter for --latest to match a specific method",
    )
    eval_parser.add_argument(
        "--sequence",
        help="Filter for --latest to match a specific sequence",
    )
    eval_parser.add_argument(
        "--association-tolerance-sec",
        type=float,
        default=0.1,
        help="Maximum allowed time difference for trajectory timestamp association",
    )
    eval_parser.add_argument(
        "--rpe-delta-m",
        type=float,
        default=1.0,
        help="Distance step delta for RPE calculations",
    )
    eval_parser.add_argument(
        "--drift-bin-width-m",
        type=float,
        default=20.0,
        help="Width of drift bins in meters",
    )
    eval_parser.add_argument(
        "--alignment-policy",
        choices=["se3", "none"],
        default="se3",
        help="Alignment policy",
    )

    # Subcommand 'compare'
    compare_parser = subparsers.add_parser("compare", help="Compare metrics across evaluated run directories")
    compare_parser.add_argument(
        "--run-dirs",
        nargs="+",
        required=True,
        help="Two or more evaluated run directories to compare",
    )
    compare_parser.add_argument(
        "--output",
        required=True,
        help="Directory where comparison artifacts are written",
    )

    # Subcommand 'convert'
    convert_parser = subparsers.add_parser(
        "convert",
        help="Export a sequence's streams to a plain layout for external baseline adapters",
    )
    convert_parser.add_argument(
        "--dataset",
        required=True,
        choices=["synthetic", "mvsec"],
        help="Dataset type",
    )
    convert_parser.add_argument(
        "--sequence",
        required=True,
        help="Name of the sequence to convert",
    )
    convert_parser.add_argument(
        "--input",
        help="Path to the input dataset (required for mvsec dataset)",
    )
    convert_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the converted streams are written",
    )
    convert_parser.add_argument(
        "--event-window-ms",
        type=float,
        default=50.0,
        help="Window length in milliseconds used when event frames are built from raw events",
    )

    # Subcommand 'validate'
    validate_parser = subparsers.add_parser("validate", help="Validate run directory artifacts and consistency")
    validate_parser.add_argument(
        "--run-dir",
        help="Path to a specific run directory to validate (required unless --latest is set)",
    )
    validate_parser.add_argument(
        "--latest",
        action="store_true",
        help="Validate the latest run directory",
    )
    validate_parser.add_argument(
        "--method",
        help="Filter for --latest to match a specific method",
    )
    validate_parser.add_argument(
        "--sequence",
        help="Filter for --latest to match a specific sequence",
    )
    validate_parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip evaluation artifact checks (for run-only directories)",
    )
    validate_parser.add_argument(
        "--output-root",
        default="runs",
        help="Root directory where run folders are stored (used with --latest)",
    )
    return parser


def _next_resume_dir(run_dir: Path, dir_name: str) -> Path:
    n = 1
    while True:
        candidate = run_dir.with_name(f"{dir_name}-r{n}")
        if not candidate.exists():
            return candidate
        n += 1


def _create_run_dir(args) -> Path:
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dir_name = f"{timestamp}_{args.method}_{args.sequence}"
    run_dir = output_root / dir_name
    if run_dir.exists() and args.resume:
        run_dir = _next_resume_dir(run_dir, dir_name)
    elif run_dir.exists():
        print(f"Error: Run directory already exists: {run_dir}", file=sys.stderr)
        sys.exit(1)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _run_logger(log_path: Path):
    def log_message(msg: str) -> None:
        formatted_time = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{formatted_time}] {msg}")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{formatted_time}] {msg}\n")

    return log_message


def _export_ensemble_artifacts(args, trajectory: Trajectory, run_dir: Path, log_message) -> None:
    if trajectory.method != "ensemble":
        return
    weight_path = run_dir / "ensemble_weights.csv"
    write_weight_log_csv(trajectory, weight_path)
    log_message(f"Exported ensemble weights to {weight_path}")
    try:
        write_ensemble_weight_plot(trajectory, run_dir / "ensemble_weights", sequence=args.sequence)
        log_message(f"Exported ensemble weight plot to {run_dir / 'ensemble_weights.png'}")
    except Exception as plot_err:
        log_message(f"WARNING: failed to write ensemble weight plot: {plot_err}")


def _export_run_artifacts(
    args,
    trajectory: Trajectory,
    config,
    run_dir: Path,
    log_message,
    *,
    event_diagnostics: EventStreamDiagnostics | None = None,
) -> None:
    csv_path = run_dir / "estimated_trajectory.csv"
    tum_path = run_dir / "estimated_trajectory_tum.txt"
    if args.method in {"rgb_vo", "event_vo"}:
        source_frame = "camera"
    elif args.method == "external":
        source_frame = "external"
    else:
        source_frame = "imu"
    metadata = ExportMetadata(source_frame=source_frame, target_frame="world")

    export_project_csv(trajectory, csv_path, metadata)
    export_tum(trajectory, tum_path, metadata)
    _export_ensemble_artifacts(args, trajectory, run_dir, log_message)
    log_message(f"Exported project CSV to {csv_path}")
    log_message(f"Exported TUM format to {tum_path}")

    manifest_path = run_dir / "run_manifest.json"
    failure_notes_path = run_dir / "failure_notes.md"
    write_run_manifest(args, config, metadata, run_dir, event_diagnostics=event_diagnostics)
    failure_notes_path.write_text(generate_failure_notes(trajectory, metadata), encoding="utf-8")
    log_message(f"Exported run manifest to {manifest_path}")
    log_message(f"Exported failure notes to {failure_notes_path}")


def _log_event_stream_health(event_diagnostics: EventStreamDiagnostics | None, log_message) -> None:
    if event_diagnostics is None:
        return
    if event_diagnostics.starved or event_diagnostics.overloaded:
        log_message(
            "WARNING: event stream health: "
            f"starved_windows={event_diagnostics.starved_window_count}, "
            f"overloaded_windows={event_diagnostics.overloaded_window_count}"
        )


def _validate_run_args(args, parser: argparse.ArgumentParser) -> None:
    if args.dataset == "mvsec" and not args.input:
        parser.error("--input is required when --dataset is 'mvsec'")
    if args.method == "external" and not args.external_trajectory:
        parser.error("--external-trajectory is required when --method is 'external'")


def _execute_run(args, run_dir: Path, log_message) -> None:
    sequence = load_dataset_sequence(args, log_message)
    event_diagnostics = sequence_event_diagnostics(sequence, window_sec=_event_window_sec(args))
    _log_event_stream_health(event_diagnostics, log_message)
    log_message("Running baseline estimator...")
    trajectory, config = run_estimator(args, sequence, run_dir=run_dir)
    log_message("Exporting trajectory artifacts...")
    _export_run_artifacts(args, trajectory, config, run_dir, log_message, event_diagnostics=event_diagnostics)
    log_message("[FINISHED] Run completed successfully.")


def _write_failed_run_artifacts(args, run_dir: Path, error: Exception) -> None:
    """Keep a failed run diagnosable: manifest with failure status plus failure notes."""
    manifest: dict[str, Any] = {
        "method": args.method,
        "dataset": args.dataset,
        "sequence": args.sequence,
        "input": getattr(args, "input", None),
        "code_version": get_code_version(),
        "status": "failed",
        "error_message": str(error),
    }
    if isinstance(error, ExternalToolError):
        manifest["external_execution"] = make_json_serializable(error.execution)
    with open(run_dir / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

    notes = f"""# Run Failure Notes

## Run Failed

- **Method**: {args.method}
- **Sequence**: {args.sequence}
- **Error**: {error}

See run.log for the full execution log.
"""
    (run_dir / "failure_notes.md").write_text(notes, encoding="utf-8")


def _handle_run_command(args, parser: argparse.ArgumentParser) -> None:
    _validate_run_args(args, parser)

    run_dir = _create_run_dir(args)
    log_message = _run_logger(run_dir / "run.log")
    log_message(f"[START] Method: {args.method}, Dataset: {args.dataset}, Sequence: {args.sequence}")
    try:
        _execute_run(args, run_dir, log_message)
    except Exception as e:
        log_message(f"[FAILED] Run failed with error: {e}")
        try:
            _write_failed_run_artifacts(args, run_dir, e)
        except Exception as write_err:
            log_message(f"WARNING: failed to write failure artifacts: {write_err}")
        raise
    if getattr(args, "evaluate", False):
        log_message("Evaluating run against ground truth...")
        _evaluate_run_dir(args, run_dir)
        log_message(f"Evaluation artifacts written to {run_dir}")


def _eval_config_from_args(args) -> EvalConfig:
    return EvalConfig(
        association_tolerance_sec=getattr(args, "association_tolerance_sec", 0.1),
        alignment_policy=getattr(args, "alignment_policy", "se3"),
        rpe_delta_m=getattr(args, "rpe_delta_m", 1.0),
        drift_bin_width_m=getattr(args, "drift_bin_width_m", 20.0),
    )


def _latest_command_run_dir(args, command_name: str) -> Path:
    run_dir = discover_latest_run_dir(Path(args.output_root), method=args.method, sequence=args.sequence)
    if run_dir is None:
        print(f"Error: No run directory found for {command_name}.", file=sys.stderr)
        sys.exit(1)
    return run_dir


def _required_command_run_dir_arg(args, parser: argparse.ArgumentParser) -> Path:
    if not args.run_dir:
        parser.error("Either --run-dir or --latest must be specified.")
    run_dir = Path(args.run_dir)
    return run_dir


def _existing_command_run_dir(run_dir: Path) -> Path:
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}", file=sys.stderr)
        sys.exit(1)
    return run_dir


def _resolve_command_run_dir(args, parser: argparse.ArgumentParser, command_name: str) -> Path:
    if args.latest:
        return _latest_command_run_dir(args, command_name)
    return _existing_command_run_dir(_required_command_run_dir_arg(args, parser))


def _update_eval_failure_manifest(run_dir: Path, reason: str) -> None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["evaluation"] = {
            "status": "failed",
            "error_message": reason,
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
    except Exception:
        pass


def _fail_eval(run_dir: Path, reason: str, eval_cfg: EvalConfig) -> NoReturn:
    print(f"Evaluation failed: {reason}", file=sys.stderr)
    try:
        write_failed_evaluation_artifacts(run_dir, reason, eval_cfg)
        _update_eval_failure_manifest(run_dir, reason)
    except Exception as write_err:
        print(f"Failed to write failure diagnostics: {write_err}", file=sys.stderr)
    sys.exit(1)


def _resolve_eval_ground_truth_path(args, run_dir: Path, eval_cfg: EvalConfig) -> Path:
    try:
        return resolve_ground_truth_path(run_dir, args.ground_truth)
    except Exception as e:
        _fail_eval(run_dir, str(e), eval_cfg)


def _load_eval_ground_truth(args, run_dir: Path, eval_cfg: EvalConfig) -> tuple[Path, Trajectory]:
    gt_path = _resolve_eval_ground_truth_path(args, run_dir, eval_cfg)
    try:
        return gt_path, load_ground_truth(gt_path)
    except Exception as e:
        _fail_eval(run_dir, f"Failed to load ground truth trajectory: {e}", eval_cfg)


def _evaluate_or_fail(args, run_dir: Path, gt_path: Path, ground_truth: Trajectory, eval_cfg: EvalConfig):
    try:
        harness_result = evaluate_run_directory(
            run_dir,
            ground_truth_path=gt_path,
            eval_config=eval_cfg,
            sequence=args.sequence or ground_truth.method,
            write_artifacts=False,
        )
        return harness_result.result
    except Exception as e:
        _fail_eval(run_dir, f"Trajectory evaluation failed: {e}", eval_cfg)


def _update_eval_success_manifest(run_dir: Path, result) -> None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["evaluation"] = {
            "status": "success",
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": make_json_serializable(result.metrics),
            "runtime": make_json_serializable(result.runtime),
            "failures": make_json_serializable(result.failures),
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
    except Exception as manifest_err:
        print(f"Warning: Failed to update run_manifest.json: {manifest_err}", file=sys.stderr)


def _write_eval_artifacts_or_fail(args, run_dir: Path, ground_truth: Trajectory, result, eval_cfg: EvalConfig) -> None:
    try:
        write_evaluation_artifacts(
            result,
            run_dir,
            sequence=args.sequence or ground_truth.method,
            warn=lambda message: print(f"Warning: {message}", file=sys.stderr),
        )
        _update_eval_success_manifest(run_dir, result)
    except Exception as e:
        _fail_eval(run_dir, f"Failed to write evaluation artifacts: {e}", eval_cfg)


def _evaluate_run_dir(args, run_dir: Path) -> None:
    eval_cfg = _eval_config_from_args(args)
    est_traj_path = run_dir / "estimated_trajectory.csv"
    if not est_traj_path.exists():
        _fail_eval(run_dir, f"Estimated trajectory not found: {est_traj_path}", eval_cfg)
    gt_path, ground_truth = _load_eval_ground_truth(args, run_dir, eval_cfg)
    result = _evaluate_or_fail(args, run_dir, gt_path, ground_truth, eval_cfg)
    _write_eval_artifacts_or_fail(args, run_dir, ground_truth, result, eval_cfg)


def _handle_eval_command(args, parser: argparse.ArgumentParser) -> None:
    run_dir = _resolve_command_run_dir(args, parser, "evaluation")
    _evaluate_run_dir(args, run_dir)
    print(f"Evaluation completed successfully. Artifacts written to {run_dir}")


def _print_validation_results(results) -> int:
    passed_count = 0
    for result in results:
        prefix = "[PASS]" if result.passed else "[FAIL]"
        print(f"{prefix} {result.check_name}: {result.message}")
        if result.passed:
            passed_count += 1
    print(f"Validation: {passed_count}/{len(results)} checks passed.")
    return passed_count


def _handle_validate_command(args, parser: argparse.ArgumentParser) -> None:
    run_dir = _resolve_command_run_dir(args, parser, "validation")
    results, all_passed = validate_run_directory(run_dir, expect_eval=not args.skip_eval)
    _print_validation_results(results)
    if not all_passed:
        sys.exit(1)


def _handle_compare_command(args, parser: argparse.ArgumentParser) -> None:
    from nav_benchmark.reporting.compare import compare_runs, write_comparison_artifacts

    try:
        summaries = compare_runs([Path(run_dir) for run_dir in args.run_dirs])
        artifact_paths = write_comparison_artifacts(summaries, Path(args.output))
    except (FileNotFoundError, ValueError) as e:
        print(f"Comparison failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Compared {len(summaries)} runs. Ranking by drift percent:")
    for rank, summary in enumerate(summaries, start=1):
        drift = "n/a" if summary.drift_percent is None else f"{summary.drift_percent:.3f}%"
        print(f"  {rank}. {summary.method} ({summary.sequence}): drift={drift}")
    for name, path in artifact_paths.items():
        print(f"Wrote {name}: {path}")


def _handle_convert_command(args, parser: argparse.ArgumentParser) -> None:
    from nav_benchmark.datasets.convert import export_sequence_streams

    if args.dataset == "mvsec" and not args.input:
        parser.error("--input is required when --dataset is 'mvsec'")

    def log_message(msg: str) -> None:
        print(msg)

    sequence = load_dataset_sequence(args, log_message)
    manifest = export_sequence_streams(sequence, Path(args.output_dir))
    stream_names = ", ".join(sorted(manifest["streams"])) or "none"
    print(f"Converted sequence '{args.sequence}' to {args.output_dir} (streams: {stream_names})")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    handlers = {
        "run": _handle_run_command,
        "eval": _handle_eval_command,
        "validate": _handle_validate_command,
        "compare": _handle_compare_command,
        "convert": _handle_convert_command,
    }
    handlers[args.command](args, parser)


if __name__ == "__main__":
    main()
