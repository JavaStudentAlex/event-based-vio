"""JEPA-lite: preprocessing, self-supervised training, signals, external adapter."""

import h5py
import numpy as np
import pytest

from nav_benchmark.jepa.external import (
    load_external_embeddings,
    obs_series_from_files,
    signals_from_embeddings,
)
from nav_benchmark.jepa.frames import (
    EGO_DIM,
    NUM_PATCHES,
    PATCH_DIM,
    ego_motion_features,
    frame_patches,
    stack_frame_patches,
    to_gray_float,
)
from nav_benchmark.jepa.model import JepaConfig, JepaModel, build_pair_dataset, train_jepa
from nav_benchmark.jepa.signals import FrameSignals, combine_stream_signals


def _moving_frames(count: int = 20, height: int = 48, width: int = 64, step: int = 3) -> np.ndarray:
    """A textured pattern translating ``step`` pixels per frame."""
    y, x = np.mgrid[0:height, 0:width]
    base = (np.sin(x * 0.35) * np.cos(y * 0.22) + 1.0) * 127.5
    return np.stack([np.roll(base, shift=k * step, axis=1) for k in range(count)], axis=0).astype(np.uint8)


def _reference_line(count: int = 20, dt: float = 0.05):
    t = np.arange(count) * dt
    positions = np.zeros((count, 3))
    positions[:, 0] = t  # 1 m/s along x
    quats = np.zeros((count, 4))
    quats[:, 3] = 1.0
    return t, positions, quats


def _tiny_config(**overrides) -> JepaConfig:
    defaults = dict(embed_dim=16, hidden_dim=32, batch_size=16, steps=80, lr=2e-3, seed=5)
    defaults.update(overrides)
    return JepaConfig(**defaults)


class TestFramePreprocessing:
    def test_gray_conversion_handles_rgb_uint8_and_float(self):
        rgb = np.full((8, 8, 3), 255, dtype=np.uint8)
        assert to_gray_float(rgb).max() == pytest.approx(1.0)
        already = np.full((8, 8), 0.25, dtype=np.float32)
        np.testing.assert_allclose(to_gray_float(already), 0.25)

    def test_patch_features_are_standardized(self):
        patches = frame_patches(_moving_frames(1)[0])
        assert patches.shape == (NUM_PATCHES, PATCH_DIM)
        np.testing.assert_allclose(patches.mean(axis=1), 0.0, atol=1e-4)

    def test_ego_motion_features_shapes_and_dt(self):
        t, positions, quats = _reference_line()
        frame_times = t[::2]
        ego = ego_motion_features(t, positions, quats, frame_times)
        assert ego.shape == (len(frame_times) - 1, EGO_DIM)
        np.testing.assert_allclose(ego[:, 6], 0.1, atol=1e-9)  # dt between every other frame
        np.testing.assert_allclose(ego[:, 0], 0.1, atol=1e-6)  # 1 m/s body-frame x translation


class TestTraining:
    def test_loss_decreases_on_consistent_motion(self):
        frames = _moving_frames()
        t, positions, quats = _reference_line()
        patches = stack_frame_patches(frames)
        ego = ego_motion_features(t, positions, quats, t)
        now, nxt, ego_pairs = build_pair_dataset([(patches, ego)])

        model = JepaModel(_tiny_config())
        history = train_jepa(model, now, nxt, ego_pairs, device="cpu")

        first = float(np.mean(history[:10]))
        last = float(np.mean(history[-10:]))
        assert last < first

    def test_pair_dataset_never_crosses_segments(self):
        frames = stack_frame_patches(_moving_frames(4))
        ego = np.zeros((3, EGO_DIM), dtype=np.float32)
        now, nxt, pairs_ego = build_pair_dataset([(frames, ego), (frames, ego)])
        assert len(now) == len(nxt) == len(pairs_ego) == 6  # 3 pairs per segment, no cross-pair

    def test_checkpoint_roundtrip_preserves_embeddings(self, tmp_path):
        import torch

        model = JepaModel(_tiny_config(steps=5))
        patches = stack_frame_patches(_moving_frames(4))
        path = tmp_path / "jepa.pt"
        model.save(path)
        restored = JepaModel.load(path)
        original = model.embed(torch.as_tensor(patches, dtype=torch.float32))
        loaded = restored.embed(torch.as_tensor(patches, dtype=torch.float32))
        np.testing.assert_allclose(original.numpy(), loaded.numpy(), rtol=0, atol=0)


class TestSignals:
    def test_embedding_speed_separates_static_from_moving(self):
        from nav_benchmark.jepa.model import embedding_speeds

        model = JepaModel(_tiny_config())
        static = np.repeat(stack_frame_patches(_moving_frames(1)), 6, axis=0)
        moving = stack_frame_patches(_moving_frames(6))
        static_speed = embedding_speeds(model, static)
        moving_speed = embedding_speeds(model, moving)
        np.testing.assert_allclose(static_speed, 0.0, atol=1e-6)
        assert moving_speed[1:].min() > 1e-4

    def test_surprise_scores_are_frame_aligned(self):
        from nav_benchmark.jepa.model import surprise_scores

        model = JepaModel(_tiny_config())
        patches = stack_frame_patches(_moving_frames(6))
        ego = np.zeros((5, EGO_DIM), dtype=np.float32)
        scores = surprise_scores(model, patches, ego)
        assert scores.shape == (6,)
        assert scores[0] == 0.0

    def test_combine_streams_forward_fills_on_union_times(self):
        rgb = FrameSignals(
            times=np.array([0.0, 1.0]), surprise=np.array([0.1, 0.2]), embedding_speed=np.array([1.0, 2.0])
        )
        event = FrameSignals(times=np.array([0.5]), surprise=np.array([0.9]), embedding_speed=np.array([4.0]))
        series = combine_stream_signals(rgb, event)
        np.testing.assert_allclose(series.times, [0.0, 0.5, 1.0])
        np.testing.assert_allclose(series.rgb_surprise, [0.1, 0.1, 0.2])
        np.testing.assert_allclose(series.event_surprise, [0.0, 0.9, 0.9])
        np.testing.assert_allclose(series.embedding_speed, [0.5, 2.5, 3.0])  # mean of ffilled streams

    def test_combine_requires_a_stream(self):
        with pytest.raises(ValueError, match="stream"):
            combine_stream_signals(None, None)


class TestExternalAdapter:
    def _write_h5(self, path, times, embeddings):
        with h5py.File(path, "w") as f:
            f.create_dataset("times", data=times)
            f.create_dataset("embeddings", data=embeddings)

    def test_h5_and_npz_roundtrip(self, tmp_path):
        times = np.array([0.0, 0.5, 1.0])
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
        h5_path = tmp_path / "emb.h5"
        npz_path = tmp_path / "emb.npz"
        self._write_h5(h5_path, times, embeddings)
        np.savez(npz_path, times=times, embeddings=embeddings)

        for path in (h5_path, npz_path):
            loaded_times, loaded_embeddings = load_external_embeddings(path)
            np.testing.assert_allclose(loaded_times, times)
            np.testing.assert_allclose(loaded_embeddings, embeddings)

    def test_signals_semantics(self):
        times = np.array([0.0, 1.0, 2.0])
        embeddings = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        signals = signals_from_embeddings(times, embeddings)
        assert signals.surprise[0] == 0.0
        assert signals.surprise[1] == pytest.approx(0.0)  # identical embeddings
        assert signals.surprise[2] == pytest.approx(1.0)  # orthogonal embeddings
        assert signals.embedding_speed[1] == 0.0
        assert signals.embedding_speed[2] > 0.0

    def test_obs_series_from_files_and_validation(self, tmp_path):
        times = np.array([0.0, 1.0])
        embeddings = np.array([[1.0, 0.0], [0.5, 0.5]])
        path = tmp_path / "rgb.h5"
        self._write_h5(path, times, embeddings)
        series = obs_series_from_files(rgb_path=path)
        assert series.rgb_surprise[1] > 0.0
        np.testing.assert_allclose(series.event_surprise, 0.0)

        with pytest.raises(ValueError, match="At least one"):
            obs_series_from_files()
        bad = tmp_path / "bad.h5"
        with h5py.File(bad, "w") as f:
            f.create_dataset("times", data=times)
        with pytest.raises(ValueError, match="embeddings"):
            load_external_embeddings(bad)
