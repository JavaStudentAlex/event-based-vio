import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Visual-Inertial Navigation Benchmark Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

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


if __name__ == "__main__":
    main()
