#!/usr/bin/env python3
"""Convert MVSEC rosbag pairs (data + ground truth) into the project's HDF5 layout.

The MVSEC distribution at https://daniilidis-group.github.io/mvsec/ ships
rosbags (``<sequence>_data.bag`` + ``<sequence>_gt.bag``). The benchmark loader
(`nav_benchmark.datasets.mvsec.load_mvsec_sequence`) reads an HDF5 layout:

    /davis/left/events/{ts,x,y,p}
    /davis/left/imu/{ts,linear_acceleration_{x,y,z},angular_velocity_{x,y,z}}
    /davis/left/pose/{ts,px,py,pz,qx,qy,qz,qw}
    /davis/left/image_raw/{ts,image_raw}          (optional, --include-images)
    /davis/left/camera_info/{K,D,P}               (when present in the bag)

This script bridges the two using the pure-Python ``rosbags`` reader (no ROS
installation needed). Timestamps are kept as absolute epoch seconds; use
``--start-sec``/``--duration-sec`` to convert a slice for faster experiments.

Example (15 s slice of indoor_flying1):

    uv run python scripts/convert_mvsec_bag_to_h5.py \\
        --data-bag data/indoor_flying1_data.bag \\
        --gt-bag data/indoor_flying1_gt.bag \\
        --output data/indoor_flying1_5s20s.h5 \\
        --start-sec 5 --duration-sec 15
"""

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from rosbags.highlevel import AnyReader

IMU_COLUMNS = (
    "ts",
    "linear_acceleration_x",
    "linear_acceleration_y",
    "linear_acceleration_z",
    "angular_velocity_x",
    "angular_velocity_y",
    "angular_velocity_z",
)
POSE_COLUMNS = ("ts", "px", "py", "pz", "qx", "qy", "qz", "qw")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-bag", required=True, help="MVSEC <sequence>_data.bag path")
    parser.add_argument("--gt-bag", help="MVSEC <sequence>_gt.bag path (optional; adds ground-truth poses)")
    parser.add_argument("--output", required=True, help="Output HDF5 path")
    parser.add_argument("--camera", default="left", choices=["left", "right"], help="DAVIS camera to extract")
    parser.add_argument(
        "--start-sec",
        type=float,
        default=0.0,
        help="Slice start, seconds relative to the data bag start time",
    )
    parser.add_argument(
        "--duration-sec",
        type=float,
        default=None,
        help="Slice duration in seconds (default: to the end of the bag)",
    )
    parser.add_argument(
        "--include-images",
        action="store_true",
        help="Also convert /davis/<camera>/image_raw frames (larger output file)",
    )
    return parser.parse_args(argv)


def _stamp_sec(header_stamp) -> float:
    return float(header_stamp.sec) + float(header_stamp.nanosec) * 1e-9


def _in_window(t: float, t_start: float, t_end: float) -> bool:
    return t_start <= t <= t_end


def _topic_messages(reader: AnyReader, topic: str):
    connections = [connection for connection in reader.connections if connection.topic == topic]
    for connection, _timestamp, rawdata in reader.messages(connections=connections):
        yield reader.deserialize(rawdata, connection.msgtype)


def _read_events(reader: AnyReader, topic: str, t_start: float, t_end: float) -> dict[str, np.ndarray]:
    rows: list[tuple[float, int, int, int]] = []
    for msg in _topic_messages(reader, topic):
        for event in msg.events:
            t = _stamp_sec(event.ts)
            if _in_window(t, t_start, t_end):
                rows.append((t, int(event.x), int(event.y), 1 if event.polarity else -1))
    rows.sort(key=lambda row: row[0])
    data = np.asarray(rows, dtype=np.float64).reshape(-1, 4)
    return {
        "ts": data[:, 0],
        "x": data[:, 1].astype(np.uint16),
        "y": data[:, 2].astype(np.uint16),
        "p": data[:, 3].astype(np.int8),
    }


def _read_stamped_rows(
    reader: AnyReader,
    topic: str,
    t_start: float,
    t_end: float,
    columns: tuple[str, ...],
    extract: Callable[[object], tuple[float, ...]],
) -> dict[str, np.ndarray]:
    """Timestamp-filtered, time-sorted per-message rows as named float64 columns."""
    rows: list[tuple[float, ...]] = []
    for msg in _topic_messages(reader, topic):
        t = _stamp_sec(msg.header.stamp)
        if _in_window(t, t_start, t_end):
            rows.append((t, *extract(msg)))
    rows.sort(key=lambda row: row[0])
    data = np.asarray(rows, dtype=np.float64).reshape(-1, len(columns))
    return {name: data[:, index] for index, name in enumerate(columns)}


def _imu_fields(msg) -> tuple[float, ...]:
    acceleration = msg.linear_acceleration
    angular = msg.angular_velocity
    return (
        float(acceleration.x),
        float(acceleration.y),
        float(acceleration.z),
        float(angular.x),
        float(angular.y),
        float(angular.z),
    )


def _pose_fields(msg) -> tuple[float, ...]:
    position = msg.pose.position
    orientation = msg.pose.orientation
    return (
        float(position.x),
        float(position.y),
        float(position.z),
        float(orientation.x),
        float(orientation.y),
        float(orientation.z),
        float(orientation.w),
    )


def _read_camera_info(reader: AnyReader, topic: str) -> dict[str, np.ndarray] | None:
    for msg in _topic_messages(reader, topic):
        # ROS1 CameraInfo uses uppercase field names, ROS2 lowercase.
        return {
            name: np.asarray(getattr(msg, name, getattr(msg, name.lower(), ())), dtype=np.float64)
            for name in ("K", "D", "P")
        }
    return None


def _read_images(reader: AnyReader, topic: str, t_start: float, t_end: float) -> tuple[np.ndarray, np.ndarray]:
    frames: list[np.ndarray] = []
    stamps: list[float] = []
    for msg in _topic_messages(reader, topic):
        t = _stamp_sec(msg.header.stamp)
        if _in_window(t, t_start, t_end):
            frames.append(np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width).copy())
            stamps.append(t)
    if not frames:
        return np.empty((0, 0, 0), dtype=np.uint8), np.empty(0, dtype=np.float64)
    order = np.argsort(np.asarray(stamps, dtype=np.float64), kind="stable")
    return np.stack(frames, axis=0)[order], np.asarray(stamps, dtype=np.float64)[order]


@dataclass
class ConvertedStreams:
    """Streams extracted from the MVSEC bags for one camera and time window."""

    events: dict[str, np.ndarray]
    imu: dict[str, np.ndarray]
    camera_info: dict[str, np.ndarray] | None = None
    images: np.ndarray | None = None
    image_ts: np.ndarray | None = None
    poses: dict[str, np.ndarray] | None = None


def _read_data_bag(args: argparse.Namespace) -> ConvertedStreams:
    camera = args.camera
    with AnyReader([Path(args.data_bag)]) as reader:
        bag_start_sec = reader.start_time / 1e9
        bag_end_sec = reader.end_time / 1e9
        t_start = bag_start_sec + args.start_sec
        t_end = bag_end_sec if args.duration_sec is None else t_start + args.duration_sec
        print(f"Converting {Path(args.data_bag).name}: window [{t_start:.3f}, {t_end:.3f}] (epoch seconds)")

        streams = ConvertedStreams(
            events=_read_events(reader, f"/davis/{camera}/events", t_start, t_end),
            imu=_read_stamped_rows(reader, f"/davis/{camera}/imu", t_start, t_end, IMU_COLUMNS, _imu_fields),
            camera_info=_read_camera_info(reader, f"/davis/{camera}/camera_info"),
        )
        print(f"  events: {len(streams.events['ts'])}")
        print(f"  imu samples: {len(streams.imu['ts'])}")
        if args.include_images:
            streams.images, streams.image_ts = _read_images(reader, f"/davis/{camera}/image_raw", t_start, t_end)
            print(f"  images: {len(streams.image_ts)}")

    streams.poses = _read_gt_bag(args, t_start, t_end)
    return streams


def _read_gt_bag(args: argparse.Namespace, t_start: float, t_end: float) -> dict[str, np.ndarray] | None:
    if not args.gt_bag:
        return None
    with AnyReader([Path(args.gt_bag)]) as reader:
        poses = _read_stamped_rows(reader, f"/davis/{args.camera}/pose", t_start, t_end, POSE_COLUMNS, _pose_fields)
    print(f"  ground-truth poses: {len(poses['ts'])}")
    return poses


def _write_group(f: h5py.File, group_name: str, datasets: dict[str, np.ndarray]) -> None:
    group = f.create_group(group_name)
    for name, values in datasets.items():
        group.create_dataset(name, data=values)


def _write_image_group(f: h5py.File, group_name: str, streams: ConvertedStreams) -> None:
    if streams.images is None or streams.image_ts is None or len(streams.image_ts) == 0:
        return
    group = f.create_group(group_name)
    group.create_dataset("ts", data=streams.image_ts)
    group.create_dataset("image_raw", data=streams.images, compression="gzip", compression_opts=4)


def _write_output(output: Path, camera: str, streams: ConvertedStreams) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output, "w") as f:
        _write_group(f, f"/davis/{camera}/events", streams.events)
        _write_group(f, f"/davis/{camera}/imu", streams.imu)
        if streams.poses is not None and len(streams.poses["ts"]) > 0:
            _write_group(f, f"/davis/{camera}/pose", streams.poses)
        if streams.camera_info is not None:
            _write_group(f, f"/davis/{camera}/camera_info", streams.camera_info)
        _write_image_group(f, f"/davis/{camera}/image_raw", streams)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = time.perf_counter()

    streams = _read_data_bag(args)
    if len(streams.events["ts"]) == 0 and len(streams.imu["ts"]) == 0:
        print("No events and no IMU samples in the requested window; nothing to write.", file=sys.stderr)
        return 1

    output = Path(args.output)
    _write_output(output, args.camera, streams)
    print(f"Wrote {output} in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
