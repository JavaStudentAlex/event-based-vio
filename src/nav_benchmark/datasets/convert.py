"""Dataset conversion stage for external baseline adapters.

Exports a loaded sequence's streams to a plain, documented on-disk layout that
external tool wrappers (UltimateSLAM, ESVO, ...) can consume or re-pack into
their native input format, without leaking external layout assumptions into
the project's core contracts:

    output_dir/
        events.csv              t,x,y,p          (seconds, pixels, +-1)
        imu.csv                 t,ax,ay,az,gx,gy,gz
        ground_truth.csv        t,x,y,z,qx,qy,qz,qw
        images/frame_NNNNNN.png
        image_timestamps.csv    frame_id,t,path
        conversion_manifest.json

Streams the sequence does not carry are simply omitted; the manifest records
what was written so adapters can fail fast on missing inputs.
"""

import csv
import json
from pathlib import Path
from typing import Any, TypeGuard

import numpy as np

from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.synthetic.imageio import save_png_rgb

CONVERSION_MANIFEST_NAME = "conversion_manifest.json"


def _write_events_csv(events: np.ndarray, path: Path) -> int:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "p"])
        for row in events:
            writer.writerow([f"{float(row['t']):.9f}", int(row["x"]), int(row["y"]), int(row["p"])])
    return len(events)


def _write_imu_csv(imu: np.ndarray, path: Path) -> int:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "ax", "ay", "az", "gx", "gy", "gz"])
        for row in imu:
            writer.writerow(
                [f"{float(row['t']):.9f}"] + [f"{float(row[k]):.9f}" for k in ("ax", "ay", "az", "gx", "gy", "gz")]
            )
    return len(imu)


def _write_ground_truth_csv(gt: np.ndarray, path: Path) -> int:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "z", "qx", "qy", "qz", "qw"])
        for row in gt:
            writer.writerow(
                [f"{float(row['t']):.9f}"] + [f"{float(row[k]):.9f}" for k in ("x", "y", "z", "qx", "qy", "qz", "qw")]
            )
    return len(gt)


def _write_images(sequence: MvsecSequence, output_dir: Path) -> int:
    images = sequence.images
    timestamps = sequence.image_timestamps
    if images is None or timestamps is None or len(images) == 0:
        return 0
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "image_timestamps.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_id", "t", "path"])
        for i, frame in enumerate(images):
            rel_path = f"images/frame_{i:06d}.png"
            save_png_rgb(frame, output_dir / rel_path)
            writer.writerow([i, f"{float(timestamps[i]):.9f}", rel_path])
    return len(images)


def _has_rows(array: np.ndarray | None) -> TypeGuard[np.ndarray]:
    return array is not None and len(array) > 0


def _manifest_for(sequence: MvsecSequence, streams: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": sequence.metadata.source_path,
        "sequence_name": sequence.metadata.sequence_name,
        "streams": streams,
        "time_ranges": {name: list(bounds) for name, bounds in sequence.metadata.time_ranges.items()},
        "units": {"time": "seconds", "position": "meters", "orientation": "quaternion xyzw"},
    }


def export_sequence_streams(sequence: MvsecSequence, output_dir: str | Path) -> dict[str, Any]:
    """Export the sequence's streams for an external adapter; returns the manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    streams: dict[str, Any] = {}
    if _has_rows(sequence.events):
        streams["events"] = {
            "path": "events.csv",
            "count": _write_events_csv(sequence.events, output_dir / "events.csv"),
        }
    if _has_rows(sequence.imu):
        streams["imu"] = {
            "path": "imu.csv",
            "count": _write_imu_csv(sequence.imu, output_dir / "imu.csv"),
        }
    if _has_rows(sequence.gt_poses):
        streams["ground_truth"] = {
            "path": "ground_truth.csv",
            "count": _write_ground_truth_csv(sequence.gt_poses, output_dir / "ground_truth.csv"),
        }
    image_count = _write_images(sequence, output_dir)
    if image_count:
        streams["images"] = {"path": "image_timestamps.csv", "count": image_count}

    manifest = _manifest_for(sequence, streams)
    with open(output_dir / CONVERSION_MANIFEST_NAME, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest
