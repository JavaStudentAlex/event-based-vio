import numpy as np

from nav_benchmark.synthetic.config import EventCameraCfg
from nav_benchmark.synthetic.rgb_to_events import frames_to_events, pair_to_events

CFG = EventCameraCfg(positive_threshold=0.2, negative_threshold=0.2, max_events_per_frame_pair=10000)
W, H = 16, 12


def test_brightness_increase_creates_positive_events():
    prev = np.full((H, W), 30, dtype=np.uint8)
    curr = np.full((H, W), 220, dtype=np.uint8)
    _, _, ps = pair_to_events(prev, curr, CFG)
    assert ps.size > 0
    assert np.all(ps == 1)


def test_brightness_decrease_creates_negative_events():
    prev = np.full((H, W), 220, dtype=np.uint8)
    curr = np.full((H, W), 30, dtype=np.uint8)
    _, _, ps = pair_to_events(prev, curr, CFG)
    assert ps.size > 0
    assert np.all(ps == -1)


def test_identical_frames_create_no_events():
    frame = np.full((H, W), 128, dtype=np.uint8)
    xs, ys, ps = pair_to_events(frame, frame, CFG)
    assert xs.size == 0 and ys.size == 0 and ps.size == 0


def test_bounds_polarity_and_timestamps():
    f0 = np.full((H, W), 30, dtype=np.uint8)
    f1 = np.full((H, W), 220, dtype=np.uint8)
    f2 = np.full((H, W), 60, dtype=np.uint8)
    events, stats = frames_to_events([f0, f1, f2], np.array([0.0, 0.1, 0.2]), CFG, W, H)
    assert events.x.min() >= 0 and events.x.max() < W
    assert events.y.min() >= 0 and events.y.max() < H
    assert set(np.unique(events.p).astype(int).tolist()).issubset({-1, 1})
    assert np.all(np.diff(events.t) >= 0)  # non-decreasing
    assert len(stats) == 2  # two frame pairs


def test_max_events_cap_is_respected():
    cfg = EventCameraCfg(positive_threshold=0.01, negative_threshold=0.01, max_events_per_frame_pair=5)
    prev = np.full((H, W), 10, dtype=np.uint8)
    curr = np.full((H, W), 240, dtype=np.uint8)
    xs, _, _ = pair_to_events(prev, curr, cfg)
    assert xs.size == 5
