"""Parse ``configs/google_earth_sequence.yaml`` into typed, validated dataclasses.

The original parsed mapping is preserved on :attr:`SequenceConfig.raw` so the recorder
can embed the full config verbatim into ``metadata/sequence.yaml`` (Phase 2 acceptance
criterion) while the metadata writer adds the documented Phase 7 fields on top.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass
class SequenceCfg:
    name: str = "ge_sequence_001"
    duration_s: float = 60.0
    output_dir: str = "data/ge_sequence_001"
    random_seed: int = 42


@dataclass
class RecordingCfg:
    capture_fps: float = 30.0
    save_rgb_frames: bool = True
    save_rgb_preview: bool = True
    preview_fps: float = 30.0
    max_missing_frame_gap_s: float = 1.0


@dataclass
class HeadingPoint:
    t_s: float
    heading_deg: float


@dataclass
class FlightCfg:
    start_lat: float = 50.4501
    start_lon: float = 30.5234
    start_alt_m: float = 100.0
    speed_mps: float = 10.0
    position_update_hz: float = 10.0
    deterministic_heading: bool = True
    start_heading_deg: float = 90.0
    heading_script: list[HeadingPoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.position_update_hz <= 0:
            raise ValueError("flight.position_update_hz must be > 0")
        # Heading script must be sorted by time for deterministic interpolation.
        times = [p.t_s for p in self.heading_script]
        if times != sorted(times):
            raise ValueError("flight.heading_script must be sorted by t_s")


@dataclass
class CameraCfg:
    model: str = "pinhole"
    width: int = 640
    height: int = 480
    fx: float = 450.0
    fy: float = 450.0
    cx: float = 320.0
    cy: float = 240.0
    distortion_model: str = "none"
    distortion_coeffs: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    note: str = "Assumed synthetic calibration, not measured Google Earth camera intrinsics."

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("camera.width and camera.height must be > 0")


@dataclass
class EventCameraCfg:
    positive_threshold: float = 0.20
    negative_threshold: float = 0.20
    refractory_period_us: float = 100.0
    output_csv: bool = True
    output_h5: bool = True
    visualization_window_ms: float = 50.0
    max_events_per_frame_pair: int = 200000

    def __post_init__(self) -> None:
        if self.positive_threshold <= 0 or self.negative_threshold <= 0:
            raise ValueError("event_camera thresholds must be > 0")
        if self.visualization_window_ms <= 0:
            raise ValueError("event_camera.visualization_window_ms must be > 0")


@dataclass
class ImuCfg:
    rate_hz: float = 200.0
    gravity_mps2: float = 9.81
    accel_noise_std: float = 0.03
    gyro_noise_std: float = 0.002
    accel_bias_walk_std: float = 0.0001
    gyro_bias_walk_std: float = 0.00001
    deterministic_noise: bool = True

    def __post_init__(self) -> None:
        if self.rate_hz <= 0:
            raise ValueError("imu.rate_hz must be > 0")


@dataclass
class ValidationCfg:
    require_nonzero_events: bool = True
    require_rgb_preview: bool = True
    require_event_preview: bool = True
    max_duration_mismatch_s: float = 0.1


@dataclass
class SequenceConfig:
    sequence: SequenceCfg = field(default_factory=SequenceCfg)
    recording: RecordingCfg = field(default_factory=RecordingCfg)
    flight: FlightCfg = field(default_factory=FlightCfg)
    camera: CameraCfg = field(default_factory=CameraCfg)
    event_camera: EventCameraCfg = field(default_factory=EventCameraCfg)
    imu: ImuCfg = field(default_factory=ImuCfg)
    validation: ValidationCfg = field(default_factory=ValidationCfg)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SequenceConfig":
        data = data or {}
        flight_data = dict(data.get("flight", {}))
        script = [HeadingPoint(**pt) for pt in flight_data.pop("heading_script", [])]
        return cls(
            sequence=SequenceCfg(**data.get("sequence", {})),
            recording=RecordingCfg(**data.get("recording", {})),
            flight=FlightCfg(heading_script=script, **flight_data),
            camera=CameraCfg(**data.get("camera", {})),
            event_camera=EventCameraCfg(**data.get("event_camera", {})),
            imu=ImuCfg(**data.get("imu", {})),
            validation=ValidationCfg(**data.get("validation", {})),
            raw=data,
        )


def load_config(path: str | Path) -> SequenceConfig:
    """Load and validate a sequence config YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return SequenceConfig.from_dict(data)
