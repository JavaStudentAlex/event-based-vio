#!/usr/bin/env python3
"""Example CLI to inspect MVSEC file metadata and diagnostics."""

import argparse
import sys
from pathlib import Path

# Add src/ to PYTHONPATH dynamically if running from local checkout
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if src_path.is_dir() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from nav_benchmark.datasets.mvsec import load_mvsec_sequence  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect MVSEC HDF5 file metadata and load diagnostics.")
    parser.add_argument(
        "--h5",
        type=str,
        required=True,
        help="Path to the MVSEC HDF5 file.",
    )
    args = parser.parse_args()

    h5_path = Path(args.h5)
    if not h5_path.is_file():
        print(f"Error: File '{h5_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading MVSEC sequence from: {h5_path}")
    try:
        seq = load_mvsec_sequence(h5_path)
    except Exception as e:
        print(f"Error loading sequence: {e}", file=sys.stderr)
        sys.exit(1)

    meta = seq.metadata
    diag = seq.diagnostics
    calib = seq.calibration

    print("\n--- Sequence Metadata ---")
    print(f"Sequence Name: {meta.sequence_name}")
    print(f"Source Path:   {meta.source_path}")

    print("\n--- Sample Counts & Time Ranges ---")
    streams = set(meta.sample_counts.keys()).union(meta.time_ranges.keys())
    if not streams:
        print("No valid streams loaded.")
    else:
        for stream in sorted(streams):
            count = meta.sample_counts.get(stream, 0)
            t_range = meta.time_ranges.get(stream, (0.0, 0.0))
            duration = t_range[1] - t_range[0]
            print(
                f"  {stream:12s} : {count:8d} samples | t = [{t_range[0]:.4f} to {t_range[1]:.4f}] (duration: {duration:.2f}s)"
            )

    print("\n--- Calibration Availability ---")
    print(f"  Intrinsics (K):             {'[OK]' if calib.intrinsics_available else '[N/A]'}")
    print(f"  Distortion (D):             {'[OK]' if calib.distortion_available else '[N/A]'}")
    print(f"  Extrinsics (P):             {'[OK]' if calib.extrinsics_available else '[N/A]'}")
    print(f"  IMU-to-Camera Transform:    {'[OK]' if calib.imu_cam_transform_available else '[N/A]'}")

    print("\n--- Load Diagnostics ---")
    print(f"  Layout Mismatch: {diag.layout_mismatch}")
    if diag.missing_streams:
        print(f"  Missing Streams: {', '.join(diag.missing_streams)}")
    else:
        print("  Missing Streams: None")

    if diag.malformed_streams:
        print(f"  Malformed Streams: {', '.join(diag.malformed_streams)}")
    else:
        print("  Malformed Streams: None")

    if diag.layout_errors:
        print("  Layout Errors/Warnings:")
        for err in diag.layout_errors:
            print(f"    - {err}")


if __name__ == "__main__":
    main()
