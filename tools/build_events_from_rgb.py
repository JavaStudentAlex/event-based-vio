#!/usr/bin/env python3
"""Build synthetic events from an existing sequence's RGB frames (Phase 5 standalone).

Usage:
    python tools/build_events_from_rgb.py data/ge_sequence_001 --config configs/google_earth_sequence.yaml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nav_benchmark.synthetic import event_visualizer
from nav_benchmark.synthetic.config import load_config
from nav_benchmark.synthetic.rgb_to_events import convert_sequence


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert RGB frames into synthetic events")
    parser.add_argument("sequence_dir", help="Path to the sequence directory")
    parser.add_argument("--config", default="configs/google_earth_sequence.yaml", help="Sequence config YAML")
    parser.add_argument("--no-preview", action="store_true", help="Skip event-frame preview mp4")
    args = parser.parse_args()

    config = load_config(args.config)
    events = convert_sequence(args.sequence_dir, config.event_camera, config.camera.width, config.camera.height)
    n_frames = event_visualizer.render(
        args.sequence_dir,
        events,
        config.event_camera,
        preview_fps=config.recording.preview_fps,
        write_preview=not args.no_preview,
    )
    print(f"Events: {len(events):,}  event frames: {n_frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
