#!/usr/bin/env python3
"""Generate preview artifacts for a recorded sequence (does not modify raw data).

Usage:
    python tools/preview_sequence.py data/ge_sequence_001

Writes preview/rgb_preview.mp4, preview/events_preview.mp4 (best-effort, needs an mp4 encoder),
and preview/trajectory_preview.png (always).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nav_benchmark.synthetic.preview import (
    write_events_preview_from_frames,
    write_rgb_preview,
    write_trajectory_preview,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate preview artifacts for a sequence")
    parser.add_argument("sequence_dir", help="Path to the sequence directory")
    parser.add_argument("--rgb-fps", type=float, default=30.0, help="RGB preview FPS")
    parser.add_argument("--events-fps", type=float, default=20.0, help="Events preview FPS")
    parser.add_argument("--no-overlay", action="store_true", help="Disable RGB telemetry overlay")
    args = parser.parse_args()

    root = Path(args.sequence_dir)
    write_rgb_preview(root, fps=args.rgb_fps, overlay=not args.no_overlay)
    write_events_preview_from_frames(root, fps=args.events_fps)
    write_trajectory_preview(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
