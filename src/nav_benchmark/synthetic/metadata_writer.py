"""Write calibration and metadata files for a sequence (Phase 7).

Produces ``calibration/{camera,imu,extrinsics}.yaml`` and ``metadata/sequence.yaml``. The
sequence metadata documents the coordinate frame, origin, event model, event thresholds, IMU
noise parameters, synthetic limitations, and tool version, and embeds the full original config
under a ``config:`` key (Phase 2: "config is copied into metadata/sequence.yaml").
"""

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from nav_benchmark.synthetic.config import SequenceConfig


@dataclass
class SequenceCounts:
    recording_duration_s: float = 0.0
    rgb_frame_count: int = 0
    event_count: int = 0
    imu_sample_count: int = 0
    ground_truth_sample_count: int = 0


def get_tool_version() -> str:
    """Best-effort tool version: git short SHA if available, else the package version."""
    git_exe = shutil.which("git")
    if git_exe:
        try:
            sha = subprocess.run(
                [git_exe, "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if sha.returncode == 0 and sha.stdout.strip():
                return f"git:{sha.stdout.strip()}"
        except Exception:
            pass
    try:
        import importlib.metadata

        return importlib.metadata.version("event-based-vio")
    except Exception:
        return "unknown"


def _dump(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


def write_camera_yaml(config: SequenceConfig, path: str | Path) -> None:
    cam = config.camera
    _dump(
        {
            "model": cam.model,
            "width": cam.width,
            "height": cam.height,
            "fx": cam.fx,
            "fy": cam.fy,
            "cx": cam.cx,
            "cy": cam.cy,
            "distortion_model": cam.distortion_model,
            "distortion_coeffs": list(cam.distortion_coeffs),
            "source": "assumed_synthetic",
            "note": cam.note,
        },
        Path(path),
    )


def write_imu_yaml(config: SequenceConfig, path: str | Path) -> None:
    imu = config.imu
    _dump(
        {
            "rate_hz": imu.rate_hz,
            "accelerometer_units": "m/s^2",
            "gyroscope_units": "rad/s",
            "gravity_mps2": imu.gravity_mps2,
            "source": "generated_from_synthetic_trajectory",
        },
        Path(path),
    )


def write_extrinsics_yaml(path: str | Path) -> None:
    _dump(
        {
            "T_cam_imu": {
                "translation_m": [0.0, 0.0, 0.0],
                "rotation_quat_xyzw": [0.0, 0.0, 0.0, 1.0],
                "assumption": "camera_and_imu_are_colocated",
            }
        },
        Path(path),
    )


def write_sequence_yaml(
    config: SequenceConfig,
    counts: SequenceCounts,
    path: str | Path,
    source: str = "google_earth_pro_synthetic",
) -> None:
    ec = config.event_camera
    imu = config.imu
    data = {
        "sequence_name": config.sequence.name,
        "source": source,
        "recording_duration_s": counts.recording_duration_s,
        "capture_fps_target": config.recording.capture_fps,
        "imu_rate_hz": imu.rate_hz,
        "event_model": "log_intensity_threshold",
        "coordinate_frame": "local_enu",
        "origin": {
            "lat": config.flight.start_lat,
            "lon": config.flight.start_lon,
            "alt_m": config.flight.start_alt_m,
        },
        "event_thresholds": {
            "positive_threshold": ec.positive_threshold,
            "negative_threshold": ec.negative_threshold,
            "refractory_period_us": ec.refractory_period_us,
        },
        "imu_noise": {
            "accel_noise_std": imu.accel_noise_std,
            "gyro_noise_std": imu.gyro_noise_std,
            "accel_bias_walk_std": imu.accel_bias_walk_std,
            "gyro_bias_walk_std": imu.gyro_bias_walk_std,
            "deterministic_noise": imu.deterministic_noise,
        },
        "counts": asdict(counts),
        "tool_version": get_tool_version(),
        "limitations": [
            "Synthetic Google Earth visual input, not real drone camera data.",
            "Assumed camera calibration, not measured intrinsics.",
            "Synthetic IMU generated from trajectory, not real inertial data.",
            "Ground truth comes from simulator state.",
        ],
        # Phase 2: the full config used for this run is preserved verbatim.
        "config": config.raw or {},
    }
    _dump(data, Path(path))


def write_all(
    output_dir: str | Path,
    config: SequenceConfig,
    counts: SequenceCounts,
    source: str = "google_earth_pro_synthetic",
) -> None:
    """Write all calibration files and the sequence metadata."""
    output_dir = Path(output_dir)
    calib = output_dir / "calibration"
    write_camera_yaml(config, calib / "camera.yaml")
    write_imu_yaml(config, calib / "imu.yaml")
    write_extrinsics_yaml(calib / "extrinsics.yaml")
    write_sequence_yaml(config, counts, output_dir / "metadata" / "sequence.yaml", source=source)
