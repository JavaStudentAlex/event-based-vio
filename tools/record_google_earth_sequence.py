#!/usr/bin/env python3
"""Record a Google Earth (or synthetic) drone sequence into a standard dataset folder.

Usage:
    python tools/record_google_earth_sequence.py \
        --duration-s 60 \
        --config configs/google_earth_sequence.yaml \
        --output data/ge_sequence_001 \
        --source synthetic        # or: google_earth (needs the archive + Google Earth Pro)

Start Google Earth Pro manually first when using --source google_earth.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nav_benchmark.data.validation import validate_sequence
from nav_benchmark.synthetic.config import load_config
from nav_benchmark.synthetic.pipeline import SOURCE_GOOGLE_EARTH, SOURCE_SYNTHETIC, build_sequence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a Google Earth / synthetic drone sequence")
    parser.add_argument("--config", default="configs/google_earth_sequence.yaml", help="Path to sequence config YAML")
    parser.add_argument("--output", default=None, help="Output sequence directory (overrides config output_dir)")
    parser.add_argument("--duration-s", type=float, default=None, help="Recording duration in seconds")
    parser.add_argument(
        "--source",
        choices=[SOURCE_SYNTHETIC, SOURCE_GOOGLE_EARTH],
        default=SOURCE_SYNTHETIC,
        help="Frame source: synthetic (headless) or google_earth (live capture)",
    )
    parser.add_argument("--archive-dir", default=None, help="Path to drone-ge-simulation-main (google_earth source)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed override")
    parser.add_argument("--no-imu-noise", action="store_true", help="Disable IMU noise/bias (deterministic)")
    return parser.parse_args()


def _apply_duration_override(config, duration_s) -> None:
    if duration_s is not None:
        config.sequence.duration_s = duration_s


def _apply_seed_override(config, seed) -> None:
    if seed is not None:
        config.sequence.random_seed = seed


def _apply_cli_overrides(config, args) -> None:
    _apply_duration_override(config, args.duration_s)
    _apply_seed_override(config, args.seed)


def _output_dir(config, args) -> Path:
    return Path(args.output) if args.output else Path(config.sequence.output_dir)


def _print_validation_errors(report) -> None:
    for err in report.errors:
        print(f"  ERROR: {err}")


def _print_sequence_report(output_dir: Path, counts, report) -> None:
    print()
    print(f"Sequence created: {output_dir}")
    print(f"RGB frames: {counts.rgb_frame_count}")
    print(f"Duration: {counts.recording_duration_s:.1f} s")
    print(f"Raw states: {counts.rgb_frame_count}")
    print(f"GT poses: {counts.ground_truth_sample_count}")
    print(f"IMU samples: {counts.imu_sample_count}")
    print(f"Events: {counts.event_count:,}")
    print(f"Validation: {'PASSED' if report.valid else 'FAILED'}")
    _print_validation_errors(report)


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    _apply_cli_overrides(config, args)
    output_dir = _output_dir(config, args)
    result = build_sequence(
        config,
        output_dir,
        source=args.source,
        archive_dir=args.archive_dir,
        add_imu_noise=not args.no_imu_noise,
    )

    report = validate_sequence(output_dir, config=config)
    _print_sequence_report(output_dir, result.counts, report)
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
