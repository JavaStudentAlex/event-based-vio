#!/usr/bin/env python3
"""Validate a recorded sequence and write metadata/validation_report.json.

Usage:
    python tools/validate_sequence.py data/ge_sequence_001
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nav_benchmark.data.validation import validate_sequence


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a recorded sequence")
    parser.add_argument("sequence_dir", help="Path to the sequence directory")
    args = parser.parse_args()

    report = validate_sequence(args.sequence_dir)

    print(f"Validation: {'PASSED' if report.valid else 'FAILED'}")
    print(f"  duration_s: {report.duration_s:.3f}")
    print(f"  rgb_frame_count: {report.rgb_frame_count}")
    print(f"  event_count: {report.event_count:,}")
    print(f"  imu_sample_count: {report.imu_sample_count}")
    print(f"  ground_truth_sample_count: {report.ground_truth_sample_count}")
    for warn in report.warnings:
        print(f"  WARNING: {warn}")
    for err in report.errors:
        print(f"  ERROR: {err}")
    print(f"Report: {Path(args.sequence_dir) / 'metadata' / 'validation_report.json'}")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
