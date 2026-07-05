"""Unit tests for phase-correlation shift estimation between event frames."""

import numpy as np
import pytest

from nav_benchmark.events.shift import estimate_frame_shift


def _textured_frame(size: int = 64, density: float = 0.08, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = np.zeros((size, size), dtype=np.uint8)
    count = int(size * size * density)
    ys = rng.integers(0, size, size=count)
    xs = rng.integers(0, size, size=count)
    frame[ys, xs] = rng.integers(80, 255, size=count).astype(np.uint8)
    return frame


class TestKnownShifts:
    @pytest.mark.parametrize("dx,dy", [(0, 0), (3, 0), (0, -4), (5, 2), (-6, -3), (10, -7)])
    def test_recovers_integer_shift(self, dx: int, dy: int):
        prev = _textured_frame()
        curr = np.roll(prev, (dy, dx), axis=(0, 1))

        estimate = estimate_frame_shift(prev, curr)

        assert estimate.valid
        assert estimate.reason == "ok"
        assert estimate.dx_px == pytest.approx(dx, abs=0.5)
        assert estimate.dy_px == pytest.approx(dy, abs=0.5)
        assert estimate.confidence > 0.5

    def test_identical_frames_give_zero_shift_and_high_confidence(self):
        frame = _textured_frame()
        estimate = estimate_frame_shift(frame, frame)
        assert estimate.valid
        assert estimate.dx_px == pytest.approx(0.0, abs=0.25)
        assert estimate.dy_px == pytest.approx(0.0, abs=0.25)
        assert estimate.confidence > 0.5

    def test_rgb_frames_are_accepted(self):
        prev = np.repeat(_textured_frame()[:, :, np.newaxis], 3, axis=2)
        curr = np.roll(prev, (2, 3), axis=(0, 1))
        estimate = estimate_frame_shift(prev, curr)
        assert estimate.valid
        assert estimate.dx_px == pytest.approx(3, abs=0.5)
        assert estimate.dy_px == pytest.approx(2, abs=0.5)

    def test_deterministic_across_calls(self):
        prev = _textured_frame(seed=11)
        curr = np.roll(prev, (4, -2), axis=(0, 1))
        first = estimate_frame_shift(prev, curr)
        second = estimate_frame_shift(prev, curr)
        assert first == second


class TestConfidenceBehavior:
    def test_unrelated_frames_score_below_matched_frames(self):
        prev = _textured_frame(seed=1)
        matched = np.roll(prev, (2, 2), axis=(0, 1))
        unrelated = _textured_frame(seed=2)

        matched_conf = estimate_frame_shift(prev, matched).confidence
        unrelated_conf = estimate_frame_shift(prev, unrelated).confidence

        assert matched_conf > unrelated_conf

    def test_sparse_activity_lowers_confidence(self):
        dense_prev = _textured_frame(density=0.08, seed=3)
        dense_curr = np.roll(dense_prev, (1, 1), axis=(0, 1))
        sparse_prev = _textured_frame(density=0.001, seed=3)
        sparse_curr = np.roll(sparse_prev, (1, 1), axis=(0, 1))

        dense_conf = estimate_frame_shift(dense_prev, dense_curr).confidence
        sparse_conf = estimate_frame_shift(sparse_prev, sparse_curr).confidence

        assert sparse_conf < dense_conf


class TestFailureModes:
    def test_empty_previous_frame(self):
        empty = np.zeros((32, 32), dtype=np.uint8)
        estimate = estimate_frame_shift(empty, _textured_frame(32))
        assert not estimate.valid
        assert estimate.reason == "empty_frame"
        assert estimate.confidence == 0.0
        assert estimate.dx_px == 0.0 and estimate.dy_px == 0.0

    def test_empty_current_frame(self):
        empty = np.zeros((32, 32), dtype=np.uint8)
        estimate = estimate_frame_shift(_textured_frame(32), empty)
        assert not estimate.valid
        assert estimate.reason == "empty_frame"

    def test_non_finite_frame(self):
        prev = _textured_frame(32).astype(np.float64)
        prev[3, 3] = np.nan
        estimate = estimate_frame_shift(prev, _textured_frame(32))
        assert not estimate.valid
        assert estimate.reason == "non_finite_frame"
        assert estimate.confidence == 0.0

    def test_frame_too_small(self):
        tiny = np.ones((2, 2), dtype=np.uint8)
        estimate = estimate_frame_shift(tiny, tiny)
        assert not estimate.valid
        assert estimate.reason == "frame_too_small"

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="shapes differ"):
            estimate_frame_shift(_textured_frame(32), _textured_frame(64))

    def test_one_dimensional_input_raises(self):
        with pytest.raises(ValueError, match="2D"):
            estimate_frame_shift(np.ones(16, dtype=np.uint8), np.ones(16, dtype=np.uint8))
