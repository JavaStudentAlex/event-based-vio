from dataclasses import dataclass, field
from pathlib import Path

import h5py  # type: ignore
import numpy as np

# Structured dtypes
EVENT_DTYPE = np.dtype([("t", np.float64), ("x", np.uint16), ("y", np.uint16), ("p", np.int8)])

IMU_DTYPE = np.dtype(
    [
        ("t", np.float64),
        ("ax", np.float64),
        ("ay", np.float64),
        ("az", np.float64),
        ("gx", np.float64),
        ("gy", np.float64),
        ("gz", np.float64),
    ]
)

POSE_DTYPE = np.dtype(
    [
        ("t", np.float64),
        ("x", np.float64),
        ("y", np.float64),
        ("z", np.float64),
        ("qx", np.float64),
        ("qy", np.float64),
        ("qz", np.float64),
        ("qw", np.float64),
    ]
)


@dataclass
class LoadDiagnostics:
    missing_streams: list[str] = field(default_factory=list)
    malformed_streams: list[str] = field(default_factory=list)
    layout_mismatch: bool = False
    layout_errors: list[str] = field(default_factory=list)


@dataclass
class Calibration:
    intrinsics_available: bool = False
    distortion_available: bool = False
    extrinsics_available: bool = False
    imu_cam_transform_available: bool = False
    data: dict[str, np.ndarray] = field(default_factory=dict)


@dataclass
class SequenceMetadata:
    source_path: str
    sequence_name: str
    time_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    sample_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class MvsecSequence:
    metadata: SequenceMetadata
    diagnostics: LoadDiagnostics
    calibration: Calibration
    events: np.ndarray | None = None
    imu: np.ndarray | None = None
    gt_poses: np.ndarray | None = None
    images: np.ndarray | None = None
    image_timestamps: np.ndarray | None = None


def _check_monotonic(ts: np.ndarray, stream_name: str, diagnostics: LoadDiagnostics) -> bool:
    if len(ts) < 2:
        return True
    diffs = np.diff(ts)
    if np.any(diffs < 0):
        diagnostics.malformed_streams.append(stream_name)
        diagnostics.layout_errors.append(f"{stream_name} timestamps are not monotonic")
        return False
    return True


def _load_events(
    f: h5py.File, diagnostics: LoadDiagnostics, time_ranges: dict, sample_counts: dict
) -> np.ndarray | None:
    if "/davis/left/events" not in f:
        diagnostics.missing_streams.append("events")
        return None
    grp = f["/davis/left/events"]
    try:
        ts = grp["ts"][:]
        x = grp["x"][:]
        y = grp["y"][:]
        p = grp["p"][:]
        if _check_monotonic(ts, "events", diagnostics):
            events = np.empty(len(ts), dtype=EVENT_DTYPE)
            events["t"] = ts
            events["x"] = x
            events["y"] = y
            events["p"] = p
            time_ranges["events"] = (float(ts[0]), float(ts[-1])) if len(ts) > 0 else (0.0, 0.0)
            sample_counts["events"] = len(ts)
            return events
    except KeyError as e:
        diagnostics.malformed_streams.append("events")
        diagnostics.layout_errors.append(f"events missing child dataset: {e}")
        diagnostics.layout_mismatch = True
    return None


def _load_imu(f: h5py.File, diagnostics: LoadDiagnostics, time_ranges: dict, sample_counts: dict) -> np.ndarray | None:
    if "/davis/left/imu" not in f:
        diagnostics.missing_streams.append("imu")
        return None
    grp = f["/davis/left/imu"]
    try:
        ts = grp["ts"][:]
        ax = grp["linear_acceleration_x"][:]
        ay = grp["linear_acceleration_y"][:]
        az = grp["linear_acceleration_z"][:]
        gx = grp["angular_velocity_x"][:]
        gy = grp["angular_velocity_y"][:]
        gz = grp["angular_velocity_z"][:]
        if _check_monotonic(ts, "imu", diagnostics):
            imu = np.empty(len(ts), dtype=IMU_DTYPE)
            imu["t"] = ts
            imu["ax"] = ax
            imu["ay"] = ay
            imu["az"] = az
            imu["gx"] = gx
            imu["gy"] = gy
            imu["gz"] = gz
            time_ranges["imu"] = (float(ts[0]), float(ts[-1])) if len(ts) > 0 else (0.0, 0.0)
            sample_counts["imu"] = len(ts)
            return imu
    except KeyError as e:
        diagnostics.malformed_streams.append("imu")
        diagnostics.layout_errors.append(f"imu missing child dataset: {e}")
        diagnostics.layout_mismatch = True
    return None


def _load_gt_poses(
    f: h5py.File, diagnostics: LoadDiagnostics, time_ranges: dict, sample_counts: dict
) -> np.ndarray | None:
    if "/davis/left/pose" not in f:
        diagnostics.missing_streams.append("gt_poses")
        return None
    grp = f["/davis/left/pose"]
    try:
        ts = grp["ts"][:]
        px = grp["px"][:]
        py = grp["py"][:]
        pz = grp["pz"][:]
        qx = grp["qx"][:]
        qy = grp["qy"][:]
        qz = grp["qz"][:]
        qw = grp["qw"][:]
        if _check_monotonic(ts, "gt_poses", diagnostics):
            gt_poses = np.empty(len(ts), dtype=POSE_DTYPE)
            gt_poses["t"] = ts
            gt_poses["x"] = px
            gt_poses["y"] = py
            gt_poses["z"] = pz
            gt_poses["qx"] = qx
            gt_poses["qy"] = qy
            gt_poses["qz"] = qz
            gt_poses["qw"] = qw
            time_ranges["gt_poses"] = (float(ts[0]), float(ts[-1])) if len(ts) > 0 else (0.0, 0.0)
            sample_counts["gt_poses"] = len(ts)
            return gt_poses
    except KeyError as e:
        diagnostics.malformed_streams.append("gt_poses")
        diagnostics.layout_errors.append(f"gt_poses missing child dataset: {e}")
        diagnostics.layout_mismatch = True
    return None


def _load_images(
    f: h5py.File, diagnostics: LoadDiagnostics, time_ranges: dict, sample_counts: dict
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if "/davis/left/image_raw" not in f:
        diagnostics.missing_streams.append("images")
        return None, None
    grp = f["/davis/left/image_raw"]
    try:
        ts = grp["ts"][:]
        imgs = grp["image_raw"][:]
        if _check_monotonic(ts, "images", diagnostics):
            time_ranges["images"] = (float(ts[0]), float(ts[-1])) if len(ts) > 0 else (0.0, 0.0)
            sample_counts["images"] = len(ts)
            return imgs, ts
    except KeyError as e:
        diagnostics.malformed_streams.append("images")
        diagnostics.layout_errors.append(f"images missing child dataset: {e}")
        diagnostics.layout_mismatch = True
    return None, None


def _load_calibration(f: h5py.File) -> Calibration:
    calibration = Calibration()
    if "/davis/left/camera_info" in f:
        grp = f["/davis/left/camera_info"]
        if "K" in grp:
            calibration.intrinsics_available = True
            calibration.data["K"] = grp["K"][:]
        if "D" in grp:
            calibration.distortion_available = True
            calibration.data["D"] = grp["D"][:]
        if "P" in grp:
            calibration.extrinsics_available = True
            calibration.data["P"] = grp["P"][:]
    if "/davis/left/imu_cam_transform" in f:
        calibration.imu_cam_transform_available = True
        calibration.data["imu_cam_transform"] = f["/davis/left/imu_cam_transform"][:]
    return calibration


def load_mvsec_sequence(h5_path: str | Path) -> MvsecSequence:
    h5_path = Path(h5_path)
    diagnostics = LoadDiagnostics()
    time_ranges: dict[str, tuple[float, float]] = {}
    sample_counts: dict[str, int] = {}

    with h5py.File(h5_path, "r") as f:
        events = _load_events(f, diagnostics, time_ranges, sample_counts)
        imu = _load_imu(f, diagnostics, time_ranges, sample_counts)
        gt_poses = _load_gt_poses(f, diagnostics, time_ranges, sample_counts)
        images, image_timestamps = _load_images(f, diagnostics, time_ranges, sample_counts)
        calibration = _load_calibration(f)

    metadata = SequenceMetadata(
        source_path=str(h5_path),
        sequence_name=h5_path.stem,
        time_ranges=time_ranges,
        sample_counts=sample_counts,
    )

    return MvsecSequence(
        metadata=metadata,
        diagnostics=diagnostics,
        calibration=calibration,
        events=events,
        imu=imu,
        gt_poses=gt_poses,
        images=images,
        image_timestamps=image_timestamps,
    )
