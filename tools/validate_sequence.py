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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a recorded sequence")
    parser.add_argument("sequence_dir", help="Path to the sequence directory")
    return parser.parse_args()


def _print_messages(label: str, messages) -> None:
    for message in messages:
        print(f"  {label}: {message}")


def _print_validation_report(sequence_dir: str, report) -> None:
    print(f"Validation: {'PASSED' if report.valid else 'FAILED'}")
    print(f"  duration_s: {report.duration_s:.3f}")
    print(f"  rgb_frame_count: {report.rgb_frame_count}")
    print(f"  event_count: {report.event_count:,}")
    print(f"  imu_sample_count: {report.imu_sample_count}")
    print(f"  ground_truth_sample_count: {report.ground_truth_sample_count}")
    _print_messages("WARNING", report.warnings)
    _print_messages("ERROR", report.errors)
    print(f"Report: {Path(sequence_dir) / 'metadata' / 'validation_report.json'}")


def main() -> int:
    args = parse_args()
    report = validate_sequence(args.sequence_dir)
    _print_validation_report(args.sequence_dir, report)
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
