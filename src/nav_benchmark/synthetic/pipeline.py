"""End-to-end sequence build: record -> ground truth -> IMU -> events -> viz -> metadata -> previews.

Keeps the CLI tools thin and the full pipeline importable/testable. The Google Earth path uses
a real-time clock and the archive frame grabber; the synthetic path uses a simulated clock and a
procedural frame source so it runs headless and deterministically.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nav_benchmark.synthetic import event_visualizer, metadata_writer, preview
from nav_benchmark.synthetic.config import SequenceConfig
from nav_benchmark.synthetic.drone_model import KinematicDroneController
from nav_benchmark.synthetic.frame_source import FrameSource, GoogleEarthFrameSource, SyntheticFrameSource
from nav_benchmark.synthetic.imu_from_trajectory import imu_from_trajectory_file
from nav_benchmark.synthetic.metadata_writer import SequenceCounts
from nav_benchmark.synthetic.recorder import Clock, RealtimeClock, SimulatedClock, record
from nav_benchmark.synthetic.rgb_to_events import convert_sequence
from nav_benchmark.synthetic.trajectory_export import export_trajectory

SOURCE_SYNTHETIC = "synthetic"
SOURCE_GOOGLE_EARTH = "google_earth"

_SOURCE_LABELS = {
    SOURCE_SYNTHETIC: "synthetic_procedural",
    SOURCE_GOOGLE_EARTH: "google_earth_pro_synthetic",
}


@dataclass
class BuildResult:
    output_dir: Path
    counts: SequenceCounts


def make_drone_and_source(config: SequenceConfig, source: str, archive_dir: str | Path | None = None):
    """Construct the deterministic drone and the requested frame source."""
    drone = KinematicDroneController(config.flight, config.sequence.random_seed)
    width, height = config.camera.width, config.camera.height
    frame_source: FrameSource
    if source == SOURCE_SYNTHETIC:
        frame_source = SyntheticFrameSource(width, height, config.flight, seed=config.sequence.random_seed)
    elif source == SOURCE_GOOGLE_EARTH:
        frame_source = GoogleEarthFrameSource(width, height, archive_dir=archive_dir)
    else:
        raise ValueError(f"unknown source: {source!r} (expected {SOURCE_SYNTHETIC!r} or {SOURCE_GOOGLE_EARTH!r})")
    return drone, frame_source


def _default_clock(source: str) -> Clock:
    return SimulatedClock() if source == SOURCE_SYNTHETIC else RealtimeClock()


def build_sequence(
    config: SequenceConfig,
    output_dir: str | Path,
    source: str = SOURCE_SYNTHETIC,
    *,
    archive_dir: str | Path | None = None,
    clock: Clock | None = None,
    add_imu_noise: bool = True,
    log: Callable[[str], None] = print,
) -> BuildResult:
    """Run the full pipeline and return aggregate counts."""
    output_dir = Path(output_dir)
    drone, frame_source = make_drone_and_source(config, source, archive_dir=archive_dir)
    clock = clock or _default_clock(source)

    # 1. Record raw RGB + state.
    rec = record(config, frame_source, drone, output_dir, clock=clock, log=log)

    # 2. Metric ground truth.
    traj = export_trajectory(
        output_dir / "metadata" / "raw_state_log.csv", output_dir / "ground_truth" / "trajectory.csv"
    )
    log(f"Ground truth: {traj.t.size} poses")

    # 3. Synthetic IMU.
    imu = imu_from_trajectory_file(
        output_dir / "ground_truth" / "trajectory.csv",
        config.imu,
        output_dir / "imu" / "imu.csv",
        random_seed=config.sequence.random_seed,
        add_noise=add_imu_noise,
    )
    log(f"IMU: {len(imu)} samples @ {config.imu.rate_hz}Hz")

    # 4. Events + event-frame visualization.
    events = convert_sequence(output_dir, config.event_camera, config.camera.width, config.camera.height)
    log(f"Events: {len(events)}")
    event_visualizer.render(output_dir, events, config.event_camera, preview_fps=config.recording.preview_fps, log=log)

    # 5. Counts + calibration/metadata.
    counts = SequenceCounts(
        recording_duration_s=rec.duration_s,
        rgb_frame_count=rec.frame_count,
        event_count=len(events),
        imu_sample_count=len(imu),
        ground_truth_sample_count=int(traj.t.size),
    )
    metadata_writer.write_all(output_dir, config, counts, source=_SOURCE_LABELS[source])

    # 6. Previews (best-effort mp4, always-on trajectory png).
    if config.recording.save_rgb_preview:
        preview.write_rgb_preview(output_dir, fps=config.recording.preview_fps, log=log)
    preview.write_trajectory_preview(output_dir, log=log)

    return BuildResult(output_dir=output_dir, counts=counts)
