import csv

import numpy as np

from nav_benchmark.synthetic.config import CameraCfg, RecordingCfg, SequenceCfg, SequenceConfig
from nav_benchmark.synthetic.imageio import load_png_rgb
from nav_benchmark.synthetic.recorder import SimulatedClock, record

W, H = 8, 6
FPS = 30.0
DURATION = 0.3  # -> 9 frames


class FakeDrone:
    def __init__(self):
        self.updated_to = []
        self._t = 0.0

    def update_to(self, t_s):
        self.updated_to.append(t_s)
        self._t = t_s

    def get_state(self):
        return {"lat": 50.0 + self._t, "lon": 30.0 + self._t, "alt": 100.0, "heading": 90.0, "speed": 10.0}


class FakeSource:
    def __init__(self, value=123):
        self.width = W
        self.height = H
        self.started = False
        self.stopped = False
        self._value = value

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def get_frame(self, state):
        # Constant sentinel frame; no overlay should ever be applied by the recorder.
        return np.full((H, W, 3), self._value, dtype=np.uint8)


def _config():
    return SequenceConfig(
        sequence=SequenceCfg(duration_s=DURATION),
        recording=RecordingCfg(capture_fps=FPS),
        camera=CameraCfg(width=W, height=H),
    )


def test_records_expected_frame_count_and_lifecycle(tmp_path):
    source = FakeSource()
    drone = FakeDrone()
    result = record(_config(), source, drone, tmp_path, clock=SimulatedClock(), log=lambda _m: None)

    assert result.frame_count == round(DURATION * FPS)
    assert source.started and source.stopped
    assert len(result.states) == result.frame_count
    assert len(drone.updated_to) == result.frame_count


def test_timestamps_strictly_increasing(tmp_path):
    result = record(_config(), FakeSource(), FakeDrone(), tmp_path, clock=SimulatedClock(), log=lambda _m: None)
    assert np.all(np.diff(result.timestamps) > 0)
    assert np.allclose(result.timestamps, np.arange(result.frame_count) / FPS)


def test_saved_frame_is_raw_without_overlay(tmp_path):
    source = FakeSource(value=200)
    record(_config(), source, FakeDrone(), tmp_path, clock=SimulatedClock(), log=lambda _m: None)
    saved = load_png_rgb(tmp_path / "rgb" / "frame_000000.png")
    assert saved.shape == (H, W, 3)
    # The exact sentinel value survives -> no telemetry overlay was burned in.
    assert np.all(saved == 200)


def test_csv_logs_written(tmp_path):
    result = record(_config(), FakeSource(), FakeDrone(), tmp_path, clock=SimulatedClock(), log=lambda _m: None)

    rgb_csv = tmp_path / "metadata" / "rgb_timestamps.csv"
    state_csv = tmp_path / "metadata" / "raw_state_log.csv"
    assert rgb_csv.exists() and state_csv.exists()

    with open(rgb_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == result.frame_count
    assert rows[0]["path"] == "rgb/frame_000000.png"

    with open(state_csv, newline="") as f:
        state_rows = list(csv.DictReader(f))
    assert len(state_rows) == result.frame_count
    assert set(state_rows[0].keys()) == {"timestamp_s", "lat", "lon", "alt_m", "heading_deg", "speed_mps"}
