import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.datasets.mvsec import (
    IMU_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
    load_mvsec_sequence,
)
from nav_benchmark.trajectory.export import export_project_csv, export_tum
from nav_benchmark.trajectory.models import ExportMetadata, Trajectory
from nav_benchmark.evaluation.metrics import (
    EvalConfig,
    evaluate_trajectory,
    export_metrics_json,
    export_error_vs_time_csv,
    export_error_vs_distance_csv,
    read_project_csv,
    make_json_serializable,
)
from nav_benchmark.evaluation.plots import (
    write_trajectory_plot,
    write_drift_over_distance_plot,
)


def get_code_version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("event-based-vio")
    except Exception:
        pass

    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path) as f:
                for line in f:
                    if line.strip().startswith("version ="):
                        return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass

    return "0.1.0"


def generate_failure_notes(trajectory: Trajectory, metadata: ExportMetadata) -> str:
    ok_count = metadata.health_counts.get("OK", 0)
    degraded_count = metadata.health_counts.get("DEGRADED", 0)
    lost_count = metadata.health_counts.get("LOST", 0)
    invalid_count = metadata.health_counts.get("INVALID", 0)

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

    degraded_lost_intervals = [item for item in intervals if item[0] in ("DEGRADED", "LOST")]

    if not degraded_lost_intervals:
        intervals_text = "No degraded or lost intervals were detected during this run."
    else:
        lines = []
        for state, t_start, t_end in degraded_lost_intervals:
            duration = t_end - t_start
            lines.append(f"- **{state}**: {t_start:.4f}s to {t_end:.4f}s (duration: {duration:.4f}s)")
        intervals_text = "\n".join(lines)

    if trajectory.method == "imu_only":
        guidance_text = (
            "IMU-only propagation accumulates integration drift rapidly without correction. "
            "It is highly recommended to fuse visual or event streams (e.g. image_imu, event_imu) "
            "to bound errors and prevent tracking loss."
        )
    else:
        guidance_text = "Monitor tracking health and investigate calibration or sync anomalies."

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


def load_dataset_sequence(args, log_message) -> MvsecSequence:
    if args.dataset == "synthetic":
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
        return load_mvsec_sequence(args.input)


def run_estimator(args, sequence) -> tuple[Trajectory, ImuOnlyConfig]:
    if args.method == "imu_only":
        config = ImuOnlyConfig()
        backend = ImuOnlyBackend()
        trajectory = backend.run(sequence, config=config)
        return trajectory, config
    else:
        raise NotImplementedError(f"Method {args.method} is not implemented")


def write_run_manifest(args, config, metadata, run_dir) -> dict:
    from nav_benchmark.trajectory.models import PoseHealth

    health_counts = {h.value: metadata.health_counts.get(h.value, 0) for h in PoseHealth}

    run_manifest = {
        "method": args.method,
        "dataset": args.dataset,
        "sequence": args.sequence,
        "input": getattr(args, "input", None),
        "config": {
            "gravity": config.gravity.tolist() if hasattr(config, "gravity") else [0.0, 0.0, 9.81],
            "initial_position": config.initial_position.tolist()
            if hasattr(config, "initial_position")
            else [0.0, 0.0, 0.0],
            "initial_orientation": config.initial_orientation.tolist()
            if hasattr(config, "initial_orientation")
            else [0.0, 0.0, 0.0, 1.0],
            "initial_velocity": config.initial_velocity.tolist()
            if hasattr(config, "initial_velocity")
            else [0.0, 0.0, 0.0],
            "degraded_time_threshold": getattr(config, "degraded_time_threshold", 5.0),
            "lost_time_threshold": getattr(config, "lost_time_threshold", 10.0),
            "degraded_drift_threshold": getattr(config, "degraded_drift_threshold", 50.0),
            "lost_drift_threshold": getattr(config, "lost_drift_threshold", 100.0),
        },
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

    manifest_path = run_dir / "run_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(run_manifest, f, indent=4)
    return run_manifest


def discover_latest_run_dir(output_root: Path, method: str | None = None, sequence: str | None = None) -> Path | None:
    if not output_root.exists():
        return None
    candidates = []
    for path in output_root.iterdir():
        if not path.is_dir():
            continue

        # Check method filter
        if method:
            manifest_path = path / "run_manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                if manifest.get("method") != method:
                    continue
            except Exception:
                continue

        # Check sequence filter
        if sequence:
            manifest_path = path / "run_manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                if manifest.get("sequence") != sequence:
                    continue
            except Exception:
                continue

        # Ensure it contains estimated_trajectory.csv
        if not (path / "estimated_trajectory.csv").exists():
            continue

        candidates.append(path)

    if not candidates:
        return None

    # Sort by modification time of estimated_trajectory.csv
    candidates.sort(key=lambda p: (p / "estimated_trajectory.csv").stat().st_mtime, reverse=True)
    return candidates[0]


def load_ground_truth(path: Path) -> Trajectory:
    if not path.exists():
        raise FileNotFoundError(f"Ground truth path does not exist: {path}")

    if path.suffix.lower() in [".h5", ".hdf5"]:
        sequence = load_mvsec_sequence(path)
        if sequence.gt_poses is None or len(sequence.gt_poses) == 0:
            raise ValueError(f"No ground-truth poses found in MVSEC file: {path}")

        gt_poses = sequence.gt_poses
        N = len(gt_poses)
        from nav_benchmark.trajectory.models import PoseHealth

        positions = np.stack([gt_poses["x"], gt_poses["y"], gt_poses["z"]], axis=1)
        orientations = np.stack([gt_poses["qx"], gt_poses["qy"], gt_poses["qz"], gt_poses["qw"]], axis=1)

        return Trajectory(
            timestamps=gt_poses["t"],
            method="ground_truth",
            positions=positions,
            orientations=orientations,
            velocities=np.zeros((N, 3)),
            confidence=np.ones(N),
            health=np.array([PoseHealth.OK.value] * N, dtype=object),
            latency_ms=np.zeros(N),
        )
    else:
        try:
            return read_project_csv(path)
        except Exception as e:
            raise ValueError(f"Failed to read ground truth from CSV: {e}") from e


def write_failed_evaluation_artifacts(run_dir: Path, reason: str, config: EvalConfig) -> None:
    failed_result = {
        "status": "failed",
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
        writer.writerow([
            "timestamp", "method", "x", "y", "z", "qx", "qy", "qz", "qw",
            "vx", "vy", "vz", "confidence", "health", "latency_ms"
        ])

    with open(run_dir / "error_vs_time.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "est_x", "est_y", "est_z",
            "gt_aligned_x", "gt_aligned_y", "gt_aligned_z",
            "error_x", "error_y", "error_z", "error_magnitude",
            "health", "association_residual"
        ])

    with open(run_dir / "error_vs_distance.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "cumulative_distance", "error_magnitude", "health",
            "association_residual", "bin_start", "bin_end"
        ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Visual-Inertial Navigation Benchmark Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand 'run'
    run_parser = subparsers.add_parser("run", help="Run baseline or ensemble estimation on dataset")
    run_parser.add_argument(
        "--method",
        required=True,
        choices=["imu_only"],
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

    args = parser.parse_args()

    if args.command == "run":
        if args.dataset == "mvsec" and not args.input:
            parser.error("--input is required when --dataset is 'mvsec'")

        # Create output-root if it doesn't exist
        output_root = Path(args.output_root)
        output_root.mkdir(parents=True, exist_ok=True)

        # Generate run directory name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        dir_name = f"{timestamp}_{args.method}_{args.sequence}"
        run_dir = output_root / dir_name

        if run_dir.exists():
            if args.resume:
                n = 1
                while True:
                    candidate = run_dir.with_name(f"{dir_name}-r{n}")
                    if not candidate.exists():
                        run_dir = candidate
                        break
                    n += 1
            else:
                print(f"Error: Run directory already exists: {run_dir}", file=sys.stderr)
                sys.exit(1)

        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "run.log"

        def log_message(msg: str) -> None:
            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{formatted_time}] {msg}")
            with open(log_path, "a") as f:
                f.write(f"[{formatted_time}] {msg}\n")

        log_message(f"[START] Method: {args.method}, Dataset: {args.dataset}, Sequence: {args.sequence}")

        try:
            # 1. Load sequence
            sequence = load_dataset_sequence(args, log_message)

            # 2. Run backend estimation
            log_message("Running baseline estimator...")
            trajectory, config = run_estimator(args, sequence)

            # 3. Export trajectory artifacts
            log_message("Exporting trajectory artifacts...")
            csv_path = run_dir / "estimated_trajectory.csv"
            tum_path = run_dir / "estimated_trajectory_tum.txt"

            metadata = ExportMetadata(
                source_frame="imu",
                target_frame="world",
            )

            export_project_csv(trajectory, csv_path, metadata)
            export_tum(trajectory, tum_path, metadata)

            log_message(f"Exported project CSV to {csv_path}")
            log_message(f"Exported TUM format to {tum_path}")

            # 4. Generate manifest and failure notes
            log_message("Generating manifest and failure notes...")
            manifest_path = run_dir / "run_manifest.json"
            failure_notes_path = run_dir / "failure_notes.md"

            write_run_manifest(args, config, metadata, run_dir)

            notes_content = generate_failure_notes(trajectory, metadata)
            failure_notes_path.write_text(notes_content, encoding="utf-8")

            log_message(f"Exported run manifest to {manifest_path}")
            log_message(f"Exported failure notes to {failure_notes_path}")
            log_message("[FINISHED] Run completed successfully.")

        except Exception as e:
            log_message(f"[FAILED] Run failed with error: {e}")
            raise

    elif args.command == "eval":
        # Determine run directory
        run_dir_path = None
        if args.latest:
            run_dir_path = discover_latest_run_dir(
                Path(args.output_root),
                method=args.method,
                sequence=args.sequence
            )
            if not run_dir_path:
                print("Error: No run directory found for evaluation.", file=sys.stderr)
                sys.exit(1)
        else:
            if not args.run_dir:
                parser.error("Either --run-dir or --latest must be specified.")
            run_dir_path = Path(args.run_dir)

        if not run_dir_path.exists():
            print(f"Error: Run directory does not exist: {run_dir_path}", file=sys.stderr)
            sys.exit(1)

        # Setup EvalConfig
        eval_cfg = EvalConfig(
            association_tolerance_sec=args.association_tolerance_sec,
            alignment_policy=args.alignment_policy,
            rpe_delta_m=args.rpe_delta_m,
            drift_bin_width_m=args.drift_bin_width_m,
        )

        # Helper to fail evaluation with writing failed artifacts
        def fail_eval(reason_str: str) -> None:
            print(f"Evaluation failed: {reason_str}", file=sys.stderr)
            try:
                write_failed_evaluation_artifacts(run_dir_path, reason_str, eval_cfg)
                # Update manifest with failure
                manifest_path = run_dir_path / "run_manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        manifest["evaluation"] = {
                            "status": "failed",
                            "error_message": reason_str,
                            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        with open(manifest_path, "w", encoding="utf-8") as f:
                            json.dump(manifest, f, indent=4)
                    except Exception:
                        pass
            except Exception as write_err:
                print(f"Failed to write failure diagnostics: {write_err}", file=sys.stderr)
            sys.exit(1)

        # 1. Read estimated trajectory first to verify the run directory contains it
        est_traj_path = run_dir_path / "estimated_trajectory.csv"
        if not est_traj_path.exists():
            fail_eval(f"Estimated trajectory not found: {est_traj_path}")

        # 2. Resolve ground truth
        gt_path_str = None
        if args.ground_truth:
            gt_path_str = args.ground_truth
        else:
            # Try to resolve from run_manifest.json
            manifest_path = run_dir_path / "run_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    gt_path_str = manifest.get("input")
                except Exception as manifest_err:
                    fail_eval(f"Failed to read input path from run_manifest.json: {manifest_err}")

            if not gt_path_str:
                fail_eval("Ground truth path not specified and could not be resolved from run_manifest.json")

        gt_path = Path(gt_path_str)
        if not gt_path.exists():
            fail_eval(f"Ground truth file not found: {gt_path}")

        try:
            estimate = read_project_csv(est_traj_path)
        except Exception as e:
            fail_eval(f"Failed to read estimated trajectory: {e}")

        # 3. Load ground truth
        try:
            ground_truth = load_ground_truth(gt_path)
        except Exception as e:
            fail_eval(f"Failed to load ground truth trajectory: {e}")

        # 4. Evaluate trajectory
        try:
            result = evaluate_trajectory(estimate, ground_truth, eval_cfg)
        except Exception as e:
            fail_eval(f"Trajectory evaluation failed: {e}")

        # 5. Write artifacts
        try:
            # metrics.json
            export_metrics_json(result, run_dir_path / "metrics.json")

            # error_vs_time.csv
            export_error_vs_time_csv(result, run_dir_path / "error_vs_time.csv")

            # error_vs_distance.csv
            export_error_vs_distance_csv(result, run_dir_path / "error_vs_distance.csv")

            # ground_truth_aligned.csv
            if result.aligned_ground_truth:
                export_project_csv(
                    result.aligned_ground_truth,
                    run_dir_path / "ground_truth_aligned.csv",
                    ExportMetadata(
                        source_frame="gt",
                        target_frame="world",
                    )
                )
            else:
                # write empty ground_truth_aligned.csv
                with open(run_dir_path / "ground_truth_aligned.csv", "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "method", "x", "y", "z", "qx", "qy", "qz", "qw",
                        "vx", "vy", "vz", "confidence", "health", "latency_ms"
                    ])

            # Plots: trajectory and drift
            seq_name = getattr(args, "sequence", None) or ground_truth.method
            write_trajectory_plot(
                result,
                run_dir_path / "trajectory_plot",
                sequence=seq_name,
                title=f"Trajectory: {estimate.method} vs Ground Truth",
            )
            try:
                write_drift_over_distance_plot(
                    result,
                    run_dir_path / "drift_plot",
                    sequence=seq_name,
                    title=f"Drift over Distance: {estimate.method}",
                )
            except Exception as plot_err:
                print(f"Warning: Drift plotting skipped or failed: {plot_err}", file=sys.stderr)

            # Update run_manifest.json with success block
            manifest_path = run_dir_path / "run_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)

                    # Convert metrics and other fields to serializable form
                    ser_metrics = make_json_serializable(result.metrics)
                    manifest["evaluation"] = {
                        "status": "success",
                        "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "metrics": ser_metrics,
                    }
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(manifest, f, indent=4)
                except Exception as manifest_err:
                    print(f"Warning: Failed to update run_manifest.json: {manifest_err}", file=sys.stderr)

            print(f"Evaluation completed successfully. Artifacts written to {run_dir_path}")

        except Exception as e:
            fail_eval(f"Failed to write evaluation artifacts: {e}")


if __name__ == "__main__":
    main()
