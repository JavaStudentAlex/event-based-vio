import argparse
import sys
import time
from pathlib import Path
import numpy as np

from nav_benchmark.baselines.imu import ImuOnlyBackend
from nav_benchmark.datasets.mvsec import (
    IMU_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
    load_mvsec_sequence,
)
from nav_benchmark.trajectory.export import export_project_csv, export_tum
from nav_benchmark.trajectory.models import ExportMetadata


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

        log_message(
            f"[START] Method: {args.method}, Dataset: {args.dataset}, Sequence: {args.sequence}"
        )

        try:
            # 1. Load sequence
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

                sequence = MvsecSequence(
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

            # 2. Run backend estimation
            log_message("Running baseline estimator...")
            if args.method == "imu_only":
                backend = ImuOnlyBackend()
                trajectory = backend.run(sequence)
            else:
                raise NotImplementedError(f"Method {args.method} is not implemented")

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
            log_message("[FINISHED] Run completed successfully.")

        except Exception as e:
            log_message(f"[FAILED] Run failed with error: {e}")
            raise


if __name__ == "__main__":
    main()
