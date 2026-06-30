"""Load generated synthetic sequence folders into the benchmark data model."""

import csv
from pathlib import Path

import numpy as np

from nav_benchmark.datasets.mvsec import (
    EVENT_DTYPE,
    IMU_DTYPE,
    POSE_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
)
from nav_benchmark.synthetic.imageio import load_png_rgb
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

_TIMESTAMP_COLUMNS = ("timestamp_s", "timestamp", "t")


def _read_dict_rows(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file is missing a header: {path}")
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file has no data rows: {path}")
    return rows, set(reader.fieldnames)


def _find_column(fieldnames: set[str], candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in fieldnames:
            return name
    return None


def _resolve_float_column(
    rows: list[dict[str, str]],
    fieldnames: set[str],
    candidates: tuple[str, ...],
    path: Path,
    default: float | None,
) -> tuple[str | None, np.ndarray | None]:
    column = _find_column(fieldnames, candidates)
    if column is not None:
        return column, None
    if default is None:
        raise ValueError(f"{path} is missing one of the required columns: {candidates}")
    return None, np.full(len(rows), default, dtype=np.float64)


def _empty_float_cell(raw: str, column: str, row_number: int, path: Path, default: float | None) -> tuple[bool, float]:
    if raw == "":
        if default is None:
            raise ValueError(f"{path} has an empty value in required column {column!r} at row {row_number}")
        return True, default
    return False, 0.0


def _parse_float_cell(raw: str, column: str, row_number: int, path: Path, default: float | None) -> float:
    is_empty, empty_value = _empty_float_cell(raw, column, row_number, path, default)
    if is_empty:
        return empty_value
    try:
        return float(raw)
    except ValueError as err:
        raise ValueError(f"{path} has a non-numeric value in column {column!r} at row {row_number}") from err


def _validate_finite_column(values: np.ndarray, column: str, path: Path) -> None:
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{path} has non-finite values in column {column!r}")


def _float_column(
    rows: list[dict[str, str]],
    fieldnames: set[str],
    candidates: tuple[str, ...],
    path: Path,
    *,
    default: float | None = None,
) -> np.ndarray:
    column, default_values = _resolve_float_column(rows, fieldnames, candidates, path, default)
    if default_values is not None:
        return default_values
    if column is None:
        raise ValueError(f"Could not resolve float column from {candidates}")

    values = np.empty(len(rows), dtype=np.float64)
    for i, row in enumerate(rows):
        raw = row.get(column, "")
        values[i] = _parse_float_cell(raw, column, i + 2, path, default)
    _validate_finite_column(values, column, path)
    return values


def _check_monotonic(timestamps: np.ndarray, path: Path) -> None:
    if timestamps.size > 1 and np.any(np.diff(timestamps) < 0.0):
        raise ValueError(f"{path} timestamps are not monotonic")


def _default_health_column(count: int) -> np.ndarray:
    return np.array([PoseHealth.OK.value] * count, dtype=object)


def _health_cell(row: dict[str, str], column: str, valid: set[str], row_number: int, path: Path) -> str:
    value = row.get(column, "") or PoseHealth.OK.value
    if value not in valid:
        raise ValueError(f"{path} has invalid health value {value!r} at row {row_number}")
    return value


def _health_column(rows: list[dict[str, str]], fieldnames: set[str], path: Path) -> np.ndarray:
    column = _find_column(fieldnames, ("health",))
    if column is None:
        return _default_health_column(len(rows))

    valid = {state.value for state in PoseHealth}
    values = [_health_cell(row, column, valid, i + 2, path) for i, row in enumerate(rows)]
    return np.array(values, dtype=object)


def _quat_from_columns(rows: list[dict[str, str]], fieldnames: set[str], path: Path) -> np.ndarray:
    return np.stack(
        [
            _float_column(rows, fieldnames, ("qx",), path),
            _float_column(rows, fieldnames, ("qy",), path),
            _float_column(rows, fieldnames, ("qz",), path),
            _float_column(rows, fieldnames, ("qw",), path),
        ],
        axis=1,
    )


def _quat_from_yaw(rows: list[dict[str, str]], fieldnames: set[str], path: Path) -> np.ndarray:
    yaw = np.radians(_float_column(rows, fieldnames, ("yaw_deg",), path))
    quat = np.zeros((yaw.size, 4), dtype=np.float64)
    quat[:, 2] = np.sin(0.5 * yaw)
    quat[:, 3] = np.cos(0.5 * yaw)
    return quat


def _identity_quaternions(count: int) -> np.ndarray:
    quat = np.zeros((count, 4), dtype=np.float64)
    quat[:, 3] = 1.0
    return quat


def _normalize_quaternion_rows(quat: np.ndarray, path: Path) -> np.ndarray:
    norms = np.linalg.norm(quat, axis=1)
    if np.any(norms == 0.0):
        raise ValueError(f"{path} has a zero-norm orientation quaternion")
    return quat / norms[:, np.newaxis]


def read_synthetic_imu_csv(path: str | Path) -> np.ndarray:
    """Read ``imu/imu.csv`` into the common IMU structured dtype."""
    path = Path(path)
    rows, fieldnames = _read_dict_rows(path)

    timestamps = _float_column(rows, fieldnames, _TIMESTAMP_COLUMNS, path)
    _check_monotonic(timestamps, path)

    imu = np.empty(timestamps.size, dtype=IMU_DTYPE)
    imu["t"] = timestamps
    imu["ax"] = _float_column(rows, fieldnames, ("ax_mps2", "ax"), path)
    imu["ay"] = _float_column(rows, fieldnames, ("ay_mps2", "ay"), path)
    imu["az"] = _float_column(rows, fieldnames, ("az_mps2", "az"), path)
    imu["gx"] = _float_column(rows, fieldnames, ("gx_radps", "gx"), path)
    imu["gy"] = _float_column(rows, fieldnames, ("gy_radps", "gy"), path)
    imu["gz"] = _float_column(rows, fieldnames, ("gz_radps", "gz"), path)
    return imu


def read_synthetic_events_csv(path: str | Path) -> np.ndarray:
    """Read ``events/events.csv`` into the common event structured dtype."""
    path = Path(path)
    rows, fieldnames = _read_dict_rows(path)

    timestamps = _float_column(rows, fieldnames, _TIMESTAMP_COLUMNS, path)
    _check_monotonic(timestamps, path)

    events = np.empty(timestamps.size, dtype=EVENT_DTYPE)
    events["t"] = timestamps
    events["x"] = _float_column(rows, fieldnames, ("x",), path).astype(np.uint16)
    events["y"] = _float_column(rows, fieldnames, ("y",), path).astype(np.uint16)
    events["p"] = _float_column(rows, fieldnames, ("polarity", "p"), path).astype(np.int8)
    return events


def _trajectory_quaternions(rows: list[dict[str, str]], fieldnames: set[str], path: Path) -> np.ndarray:
    if all(name in fieldnames for name in ("qx", "qy", "qz", "qw")):
        quat = _quat_from_columns(rows, fieldnames, path)
    elif "yaw_deg" in fieldnames:
        quat = _quat_from_yaw(rows, fieldnames, path)
    else:
        quat = _identity_quaternions(len(rows))
    return _normalize_quaternion_rows(quat, path)


def read_synthetic_ground_truth_csv(path: str | Path) -> Trajectory:
    """Read synthetic ``ground_truth/trajectory.csv`` or compact task CSV into a Trajectory."""
    path = Path(path)
    rows, fieldnames = _read_dict_rows(path)

    timestamps = _float_column(rows, fieldnames, _TIMESTAMP_COLUMNS, path)
    _check_monotonic(timestamps, path)

    positions = np.stack(
        [
            _float_column(rows, fieldnames, ("x_m", "x"), path),
            _float_column(rows, fieldnames, ("y_m", "y"), path),
            _float_column(rows, fieldnames, ("z_m", "z"), path),
        ],
        axis=1,
    )
    orientations = _trajectory_quaternions(rows, fieldnames, path)
    velocities = np.stack(
        [
            _float_column(rows, fieldnames, ("vx_mps", "vx"), path, default=0.0),
            _float_column(rows, fieldnames, ("vy_mps", "vy"), path, default=0.0),
            _float_column(rows, fieldnames, ("vz_mps", "vz"), path, default=0.0),
        ],
        axis=1,
    )

    return Trajectory(
        timestamps=timestamps,
        method="ground_truth",
        positions=positions,
        orientations=orientations,
        velocities=velocities,
        confidence=_float_column(rows, fieldnames, ("confidence",), path, default=1.0),
        health=_health_column(rows, fieldnames, path),
        latency_ms=_float_column(rows, fieldnames, ("latency_ms",), path, default=0.0),
    )


def trajectory_to_pose_array(trajectory: Trajectory) -> np.ndarray:
    """Convert a Trajectory into the MVSEC-style pose structured dtype."""
    poses = np.empty(trajectory.timestamps.size, dtype=POSE_DTYPE)
    poses["t"] = trajectory.timestamps
    poses["x"] = trajectory.positions[:, 0]
    poses["y"] = trajectory.positions[:, 1]
    poses["z"] = trajectory.positions[:, 2]
    poses["qx"] = trajectory.orientations[:, 0]
    poses["qy"] = trajectory.orientations[:, 1]
    poses["qz"] = trajectory.orientations[:, 2]
    poses["qw"] = trajectory.orientations[:, 3]
    return poses


def _timestamped_image_rows(timestamp_path: Path) -> tuple[list[float], list[str]]:
    rows, fieldnames = _read_dict_rows(timestamp_path)
    timestamp_col = _find_column(fieldnames, _TIMESTAMP_COLUMNS)
    if timestamp_col is None:
        raise ValueError(f"{timestamp_path} is missing a timestamp column")
    path_col = _find_column(fieldnames, ("path", "image_path", "frame_path"))
    if path_col is None:
        raise ValueError(f"{timestamp_path} is missing an image path column")

    timestamps: list[float] = []
    rel_paths: list[str] = []
    for i, row in enumerate(rows):
        try:
            timestamps.append(float(row[timestamp_col]))
        except ValueError as err:
            raise ValueError(f"{timestamp_path} has non-numeric timestamp at row {i + 2}") from err
        rel_paths.append(row[path_col])

    ts = np.asarray(timestamps, dtype=np.float64)
    _check_monotonic(ts, timestamp_path)
    return timestamps, rel_paths


def _image_sequence_paths(
    root: Path,
    directory: Path,
    timestamp_path: Path | None,
    fallback_glob: str,
) -> tuple[list[Path], list[float], list[str]]:
    if timestamp_path is not None and timestamp_path.exists():
        timestamps, rel_paths = _timestamped_image_rows(timestamp_path)
        return [root / rel for rel in rel_paths], timestamps, rel_paths
    paths = sorted(directory.glob(fallback_glob))
    timestamps = [float(i) for i in range(len(paths))]
    return paths, timestamps, [str(path.relative_to(root)) for path in paths]


def _load_image_frames(root: Path, paths: list[Path], rel_paths: list[str]) -> tuple[list[np.ndarray], list[str]]:
    images = []
    resolved_rel_paths = []
    for path, _rel in zip(paths, rel_paths, strict=True):
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Referenced image frame not found: {resolved}")
        images.append(load_png_rgb(resolved))
        resolved_rel_paths.append(str(resolved.relative_to(root)))
    return images, resolved_rel_paths


def _read_image_sequence(
    root: Path,
    image_dir: str,
    timestamp_path: Path | None,
    *,
    fallback_glob: str = "*.png",
) -> tuple[np.ndarray | None, np.ndarray | None, list[str]]:
    directory = root / image_dir
    if not directory.exists():
        return None, None, []

    paths, timestamps, rel_paths = _image_sequence_paths(root, directory, timestamp_path, fallback_glob)
    if not paths:
        return None, None, []

    images, resolved_rel_paths = _load_image_frames(root, paths, rel_paths)
    return np.stack(images, axis=0), np.asarray(timestamps, dtype=np.float64), resolved_rel_paths


def _event_frame_timestamps_from_metadata(timestamp_path: Path, frame_count: int) -> np.ndarray | None:
    if not timestamp_path.exists():
        return None
    rows, fieldnames = _read_dict_rows(timestamp_path)
    event_time_col = _find_column(fieldnames, ("t_event_s", "timestamp_s", "timestamp", "t"))
    if event_time_col is None or len(rows) != frame_count:
        return None
    values = np.array([float(row[event_time_col]) for row in rows], dtype=np.float64)
    _check_monotonic(values, timestamp_path)
    return values


def _can_interpolate_event_frame_timestamps(frame_count: int, events: np.ndarray | None) -> bool:
    return events is not None and len(events) > 0 and frame_count > 1


def _event_frame_timestamps_from_events(frame_count: int, events: np.ndarray | None) -> np.ndarray | None:
    if not _can_interpolate_event_frame_timestamps(frame_count, events):
        return None
    if events is None:
        return None
    return np.linspace(float(events["t"][0]), float(events["t"][-1]), frame_count, dtype=np.float64)


def _read_event_frame_timestamps(root: Path, frame_count: int, events: np.ndarray | None) -> np.ndarray:
    timestamp_path = root / "metadata" / "event_timestamps.csv"
    timestamps = _event_frame_timestamps_from_metadata(timestamp_path, frame_count)
    if timestamps is not None:
        return timestamps
    timestamps = _event_frame_timestamps_from_events(frame_count, events)
    return timestamps if timestamps is not None else np.arange(frame_count, dtype=np.float64)


def _time_range(timestamps: np.ndarray) -> tuple[float, float]:
    if timestamps.size == 0:
        return (0.0, 0.0)
    return (float(timestamps[0]), float(timestamps[-1]))


def _resolve_synthetic_paths(path: Path) -> tuple[Path, Path, Path, Path]:
    if path.is_dir():
        return path, path / "imu" / "imu.csv", path / "ground_truth" / "trajectory.csv", path / "events" / "events.csv"

    root = path.parent.parent if path.parent.name == "imu" else path.parent
    return root, path, root / "ground_truth" / "trajectory.csv", root / "events" / "events.csv"


def _register_stream(
    time_ranges: dict[str, tuple[float, float]],
    sample_counts: dict[str, int],
    name: str,
    timestamps: np.ndarray,
) -> None:
    time_ranges[name] = _time_range(timestamps)
    sample_counts[name] = int(timestamps.size)


def _load_ground_truth_stream(
    gt_path: Path,
    diagnostics: LoadDiagnostics,
    time_ranges: dict[str, tuple[float, float]],
    sample_counts: dict[str, int],
) -> np.ndarray | None:
    if not gt_path.exists():
        diagnostics.missing_streams.append("gt_poses")
        return None
    gt = read_synthetic_ground_truth_csv(gt_path)
    _register_stream(time_ranges, sample_counts, "gt_poses", gt.timestamps)
    return trajectory_to_pose_array(gt)


def _load_events_stream(
    events_path: Path,
    diagnostics: LoadDiagnostics,
    time_ranges: dict[str, tuple[float, float]],
    sample_counts: dict[str, int],
) -> np.ndarray | None:
    if not events_path.exists():
        diagnostics.missing_streams.append("events")
        return None
    events = read_synthetic_events_csv(events_path)
    _register_stream(time_ranges, sample_counts, "events", events["t"])
    return events


def _load_rgb_stream(
    root: Path,
    diagnostics: LoadDiagnostics,
    time_ranges: dict[str, tuple[float, float]],
    sample_counts: dict[str, int],
) -> tuple[np.ndarray | None, np.ndarray | None, list[str]]:
    images, image_timestamps, image_paths = _read_image_sequence(root, "rgb", root / "metadata" / "rgb_timestamps.csv")
    if images is None or image_timestamps is None:
        diagnostics.missing_streams.append("images")
        return images, image_timestamps, image_paths
    _register_stream(time_ranges, sample_counts, "images", image_timestamps)
    return images, image_timestamps, image_paths


def _load_event_frame_stream(
    root: Path,
    events: np.ndarray | None,
    diagnostics: LoadDiagnostics,
    time_ranges: dict[str, tuple[float, float]],
    sample_counts: dict[str, int],
) -> tuple[np.ndarray | None, np.ndarray | None, list[str]]:
    event_frames, event_frame_timestamps, event_frame_paths = _read_image_sequence(
        root,
        "events/event_frames",
        None,
        fallback_glob="*.png",
    )
    if event_frames is None:
        diagnostics.missing_streams.append("event_frames")
        return event_frames, event_frame_timestamps, event_frame_paths
    event_frame_timestamps = _read_event_frame_timestamps(root, int(event_frames.shape[0]), events)
    _register_stream(time_ranges, sample_counts, "event_frames", event_frame_timestamps)
    return event_frames, event_frame_timestamps, event_frame_paths


def load_synthetic_sequence(path: str | Path, sequence_name: str | None = None) -> MvsecSequence:
    """Load a generated synthetic sequence directory into ``MvsecSequence``."""
    root, imu_path, gt_path, events_path = _resolve_synthetic_paths(Path(path))
    diagnostics = LoadDiagnostics()
    time_ranges: dict[str, tuple[float, float]] = {}
    sample_counts: dict[str, int] = {}

    imu = read_synthetic_imu_csv(imu_path)
    time_ranges["imu"] = _time_range(imu["t"])
    sample_counts["imu"] = int(imu.size)

    gt_poses = _load_ground_truth_stream(gt_path, diagnostics, time_ranges, sample_counts)
    images, image_timestamps, image_paths = _load_rgb_stream(root, diagnostics, time_ranges, sample_counts)
    events = _load_events_stream(events_path, diagnostics, time_ranges, sample_counts)
    event_frames, event_frame_timestamps, event_frame_paths = _load_event_frame_stream(
        root, events, diagnostics, time_ranges, sample_counts
    )

    return MvsecSequence(
        metadata=SequenceMetadata(
            source_path=str(root),
            sequence_name=sequence_name or root.name,
            time_ranges=time_ranges,
            sample_counts=sample_counts,
        ),
        diagnostics=diagnostics,
        calibration=Calibration(),
        events=events,
        imu=imu,
        gt_poses=gt_poses,
        images=images,
        image_timestamps=image_timestamps,
        event_frames=event_frames,
        event_frame_timestamps=event_frame_timestamps,
        image_paths=image_paths,
        event_frame_paths=event_frame_paths,
    )
