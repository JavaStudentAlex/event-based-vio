import csv

import numpy as np

from nav_benchmark.baselines.event_imu import EventImuBackend, EventImuConfig
from nav_benchmark.baselines.image_imu import ImageImuBackend, ImageImuConfig
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.baselines.multimodal_vio import MultimodalVioBackend, MultimodalVioConfig
from nav_benchmark.baselines.visual import EventVoBackend, FeatureVoConfig, RgbVoBackend
from nav_benchmark.datasets.synthetic import load_synthetic_sequence
from nav_benchmark.ensemble.confidence_weighted import fuse_trajectories, write_weight_log_csv
from nav_benchmark.evaluation.metrics import read_project_csv
from nav_benchmark.synthetic.imageio import save_png_rgb
from nav_benchmark.trajectory.export import export_project_csv


def _texture_frame(shift_x: int, shift_y: int, size: int = 96) -> np.ndarray:
    frame = np.zeros((size, size, 3), dtype=np.uint8)
    for i in range(12):
        x = (8 + i * 7 + shift_x) % size
        y = (12 + i * 5 + shift_y) % size
        frame[y : min(y + 5, size), x : min(x + 5, size), 0] = 255
        frame[y : min(y + 5, size), x : min(x + 5, size), 1] = 180
    for i in range(0, size, 16):
        frame[(i + shift_y) % size, :, 2] = 220
        frame[:, (i + shift_x) % size, 1] = 160
    return frame


def _write_visual_sequence(root) -> None:
    for name in ("rgb", "events/event_frames", "metadata", "imu", "ground_truth", "events"):
        (root / name).mkdir(parents=True, exist_ok=True)

    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]
    with open(root / "metadata" / "rgb_timestamps.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_id", "timestamp_s", "path"])
        for i, timestamp in enumerate(timestamps):
            path = f"rgb/frame_{i:06d}.png"
            save_png_rgb(_texture_frame(i * 3, i * 2), root / path)
            writer.writerow([i, timestamp, path])

    with open(root / "metadata" / "event_timestamps.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_pair", "t_prev_s", "t_curr_s", "t_event_s", "num_events"])
        for i, timestamp in enumerate(timestamps):
            writer.writerow([i, max(timestamp - 1.0, 0.0), timestamp, timestamp, 600])
            event_path = root / "events" / "event_frames" / f"event_frame_{i:06d}.png"
            save_png_rgb(_texture_frame(i * 2, i * 3), event_path)

    with open(root / "events" / "events.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "x", "y", "polarity"])
        for timestamp in timestamps:
            for j in range(600):
                writer.writerow([timestamp, j % 96, (j * 7) % 96, 1 if j % 2 == 0 else -1])

    with open(root / "imu" / "imu.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps"])
        for timestamp in timestamps:
            writer.writerow([timestamp, 0.0, 0.0, -9.81, 0.0, 0.0, 0.0])

    with open(root / "ground_truth" / "trajectory.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "x_m", "y_m", "z_m", "qx", "qy", "qz", "qw", "vx_mps", "vy_mps", "vz_mps"])
        rows = [
            [0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0, 100.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.2, 0.0],
            [2.0, 2.0, 0.2, 100.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.2, 0.0],
            [3.0, 3.0, 0.5, 100.1, 0.0, 0.0, 0.0, 1.0, 1.0, 0.3, 0.1],
            [4.0, 4.0, 0.9, 100.1, 0.0, 0.0, 0.0, 1.0, 1.0, 0.4, 0.0],
        ]
        writer.writerows(rows)


def test_synthetic_loader_reads_visual_and_event_streams(tmp_path):
    _write_visual_sequence(tmp_path)
    sequence = load_synthetic_sequence(tmp_path, sequence_name="visual_unit")

    assert sequence.images is not None
    assert sequence.event_frames is not None
    assert sequence.events is not None
    assert sequence.metadata.sample_counts["images"] == 5
    assert sequence.metadata.sample_counts["event_frames"] == 5
    assert sequence.metadata.sample_counts["events"] == 3000
    np.testing.assert_allclose(sequence.image_timestamps, [0.0, 1.0, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(sequence.event_frame_timestamps, [0.0, 1.0, 2.0, 3.0, 4.0])


def test_visual_event_event_imu_and_ensemble_outputs(tmp_path):
    _write_visual_sequence(tmp_path)
    sequence = load_synthetic_sequence(tmp_path, sequence_name="visual_unit")

    visual_config = FeatureVoConfig(
        min_matches=4,
        min_inliers=2,
        full_confidence_matches=20,
        debug_match_dir=tmp_path / "debug_matches",
    )
    imu_config = ImuOnlyConfig(gravity=np.array([0.0, 0.0, -9.81]))

    imu = ImuOnlyBackend().run(sequence, config=imu_config)
    rgb = RgbVoBackend().run(sequence, config=visual_config)
    event = EventVoBackend().run(sequence, config=visual_config)
    event_imu = EventImuBackend().run(
        sequence,
        config=EventImuConfig(imu_config=imu_config, event_vo_config=visual_config),
    )
    default_event_imu = EventImuBackend().run(sequence, config=EventImuConfig(event_vo_config=visual_config))
    image_imu = ImageImuBackend().run(
        sequence,
        config=ImageImuConfig(imu_config=imu_config, rgb_vo_config=visual_config),
    )
    multimodal = MultimodalVioBackend().run(
        sequence,
        config=MultimodalVioConfig(
            imu_config=imu_config,
            rgb_vo_config=visual_config,
            event_vo_config=visual_config,
        ),
    )

    assert rgb.method == "rgb_vo"
    assert event.method == "event_vo"
    assert event_imu.method == "event_imu"
    assert default_event_imu.method == "event_imu"
    assert image_imu.method == "image_imu"
    assert multimodal.method == "multimodal_vio"
    assert np.all(np.isfinite(rgb.positions))
    assert np.all((rgb.confidence >= 0.0) & (rgb.confidence <= 1.0))
    assert any((tmp_path / "debug_matches").glob("*.png"))
    assert len(event_imu.timestamps) == len(sequence.imu)
    assert len(default_event_imu.timestamps) == len(sequence.imu)
    assert len(image_imu.timestamps) == len(sequence.imu)
    assert len(multimodal.timestamps) == len(sequence.imu)
    assert np.all(np.isfinite(multimodal.positions))
    assert np.all((multimodal.confidence >= 0.0) & (multimodal.confidence <= 1.0))

    ensemble = fuse_trajectories(
        {
            "imu_only": imu,
            "rgb_vo": rgb,
            "event_vo": event,
            "event_imu": event_imu,
            "image_imu": image_imu,
            "multimodal_vio": multimodal,
        }
    )

    assert ensemble.method == "ensemble"
    assert set(ensemble.extra_columns) == {"w_imu", "w_rgb", "w_event", "w_event_imu", "w_image_imu", "w_multimodal"}
    weights = np.stack(
        [
            ensemble.extra_columns[name]
            for name in ("w_imu", "w_rgb", "w_event", "w_event_imu", "w_image_imu", "w_multimodal")
        ],
        axis=1,
    )
    np.testing.assert_allclose(np.sum(weights, axis=1), np.ones(len(ensemble.timestamps)))

    export_path = tmp_path / "ensemble.csv"
    export_project_csv(ensemble, export_path)
    with open(export_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert set(header[-6:]) == {"w_imu", "w_rgb", "w_event", "w_event_imu", "w_image_imu", "w_multimodal"}

    read_back = read_project_csv(export_path)
    assert read_back.method == "ensemble"
    assert len(read_back.timestamps) == len(ensemble.timestamps)

    weight_path = tmp_path / "ensemble_weights.csv"
    write_weight_log_csv(ensemble, weight_path)
    with open(weight_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["timestamp", "w_imu", "w_rgb", "w_event", "w_event_imu", "w_image_imu", "w_multimodal"]
    assert len(rows) == len(ensemble.timestamps) + 1
