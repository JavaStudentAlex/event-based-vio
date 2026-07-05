"""Behavioral tests for the event-frame shift correction Event+IMU backend."""

import numpy as np
import pytest

from nav_benchmark.baselines.event_imu import EventImuBackend, EventImuConfig
from nav_benchmark.baselines.imu import ImuOnlyBackend, ImuOnlyConfig
from nav_benchmark.datasets.mvsec import (
    IMU_DTYPE,
    Calibration,
    LoadDiagnostics,
    MvsecSequence,
    SequenceMetadata,
)
from nav_benchmark.trajectory.models import PoseHealth


def _textured_frame(size: int = 64, density: float = 0.08, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = np.zeros((size, size), dtype=np.uint8)
    count = int(size * size * density)
    ys = rng.integers(0, size, size=count)
    xs = rng.integers(0, size, size=count)
    frame[ys, xs] = rng.integers(80, 255, size=count).astype(np.uint8)
    return frame


def _imu_at_rest(duration_sec: float = 2.0, rate_hz: float = 100.0, accel_bias_x: float = 0.0) -> np.ndarray:
    count = int(duration_sec * rate_hz)
    imu = np.empty(count, dtype=IMU_DTYPE)
    imu["t"] = np.arange(count) / rate_hz
    imu["ax"] = accel_bias_x
    imu["ay"] = 0.0
    imu["az"] = 9.81
    imu["gx"] = 0.0
    imu["gy"] = 0.0
    imu["gz"] = 0.0
    return imu


def _static_scene_sequence(
    *,
    accel_bias_x: float = 0.2,
    frame_count: int = 40,
    duration_sec: float = 2.0,
    frames: np.ndarray | None = None,
) -> MvsecSequence:
    """A stationary platform whose IMU drifts, watched by a static event scene."""
    if frames is None:
        base = _textured_frame()
        frames = np.repeat(base[np.newaxis], frame_count, axis=0)
    timestamps = np.linspace(0.025, duration_sec - 0.025, len(frames))
    return MvsecSequence(
        metadata=SequenceMetadata(source_path="unit", sequence_name="static_scene"),
        diagnostics=LoadDiagnostics(),
        calibration=Calibration(),
        imu=_imu_at_rest(duration_sec=duration_sec, accel_bias_x=accel_bias_x),
        event_frames=frames,
        event_frame_timestamps=timestamps,
    )


def _final_drift_m(trajectory) -> float:
    return float(np.linalg.norm(trajectory.positions[-1]))


class TestEventCorrectionEffect:
    def test_static_event_scene_bounds_imu_drift(self):
        sequence = _static_scene_sequence()
        imu_only = ImuOnlyBackend().run(sequence, config=ImuOnlyConfig())
        event_imu = EventImuBackend().run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))

        assert _final_drift_m(event_imu) < _final_drift_m(imu_only)
        assert np.all(np.isfinite(event_imu.positions))

    def test_runs_without_ground_truth(self):
        sequence = _static_scene_sequence()
        assert sequence.gt_poses is None
        trajectory = EventImuBackend().run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))
        assert trajectory.method == "event_imu"
        assert len(trajectory.timestamps) == len(sequence.imu)

    def test_deterministic(self):
        config = EventImuConfig(imu_config=ImuOnlyConfig())
        first = EventImuBackend().run(_static_scene_sequence(), config=config)
        second = EventImuBackend().run(_static_scene_sequence(), config=config)
        np.testing.assert_array_equal(first.positions, second.positions)
        np.testing.assert_array_equal(first.confidence, second.confidence)
        assert list(first.health) == list(second.health)

    def test_correction_is_norm_bounded_per_frame(self):
        cap = 0.001
        sequence = _static_scene_sequence(accel_bias_x=5.0)
        imu_only = ImuOnlyBackend().run(sequence, config=ImuOnlyConfig())
        event_imu = EventImuBackend().run(
            sequence,
            config=EventImuConfig(imu_config=ImuOnlyConfig(), max_correction_m_per_frame=cap),
        )

        pair_count = len(sequence.event_frame_timestamps) - 1
        total_offset = np.linalg.norm(event_imu.positions - imu_only.positions, axis=1)
        assert float(total_offset.max()) <= cap * pair_count + 1e-9

    def test_health_ok_while_corrections_active(self):
        sequence = _static_scene_sequence(accel_bias_x=0.0)
        trajectory = EventImuBackend().run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))
        frame_t = sequence.event_frame_timestamps
        covered = (trajectory.timestamps > frame_t[0]) & (trajectory.timestamps <= frame_t[-1])
        covered_health = [str(h) for h in trajectory.health[covered]]
        assert covered_health.count(PoseHealth.OK.value) > 0.9 * len(covered_health)


class TestFailureVisibility:
    def test_empty_event_frames_leave_imu_backbone_untouched(self):
        frames = np.zeros((40, 64, 64), dtype=np.uint8)
        sequence = _static_scene_sequence(frames=frames)
        imu_only = ImuOnlyBackend().run(sequence, config=ImuOnlyConfig())
        event_imu = EventImuBackend().run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))

        np.testing.assert_array_equal(event_imu.positions, imu_only.positions)
        # No usable event cue: confidence stays at the IMU floor, never OK.
        assert PoseHealth.OK.value not in {str(h) for h in event_imu.health[1:]}

    def test_invalid_event_frames_skip_corrections(self):
        frames = np.repeat(_textured_frame()[np.newaxis].astype(np.float64), 40, axis=0)
        frames[:, 5, 5] = np.nan
        sequence = _static_scene_sequence(frames=frames)
        imu_only = ImuOnlyBackend().run(sequence, config=ImuOnlyConfig())

        backend = EventImuBackend()
        event_imu = backend.run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))

        np.testing.assert_array_equal(event_imu.positions, imu_only.positions)
        assert backend.diagnostics["corrected_pair_count"] == 0
        assert backend.diagnostics["invalid_pair_count"] == len(frames) - 1

    def test_poor_overlap_degrades_uncovered_samples(self):
        base = _textured_frame()
        frames = np.repeat(base[np.newaxis], 10, axis=0)
        sequence = _static_scene_sequence(frames=frames, duration_sec=4.0, accel_bias_x=0.0)
        # Frames cover only the first ~1 s of a 4 s IMU stream.
        sequence.event_frame_timestamps = np.linspace(0.025, 0.975, 10)

        config = EventImuConfig(imu_config=ImuOnlyConfig(), max_frame_gap_sec=0.25)
        trajectory = EventImuBackend().run(sequence, config=config)

        uncovered = trajectory.timestamps > 1.25
        uncovered_health = {str(h) for h in trajectory.health[uncovered]}
        assert PoseHealth.OK.value not in uncovered_health
        np.testing.assert_allclose(trajectory.confidence[uncovered], config.base_imu_confidence)

    def test_low_confidence_cue_skips_correction(self):
        sequence = _static_scene_sequence(accel_bias_x=1.0)
        imu_only = ImuOnlyBackend().run(sequence, config=ImuOnlyConfig())
        config = EventImuConfig(imu_config=ImuOnlyConfig(), min_shift_confidence=1.1)
        event_imu = EventImuBackend().run(sequence, config=config)
        np.testing.assert_array_equal(event_imu.positions, imu_only.positions)

    def test_non_finite_imu_backbone_skips_corrections(self):
        sequence = _static_scene_sequence()
        imu = sequence.imu.copy()
        imu["ax"] = np.nan
        sequence.imu = imu

        backend = EventImuBackend()
        backend.run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))

        # NaN propagation makes every innovation non-finite; no correction applies.
        assert backend.diagnostics["corrected_pair_count"] == 0
        assert backend.diagnostics["invalid_pair_count"] == backend.diagnostics["event_pair_count"]

    def test_non_positive_frame_dt_skips_pair(self):
        sequence = _static_scene_sequence()
        timestamps = sequence.event_frame_timestamps.copy()
        timestamps[1] = timestamps[0]
        sequence.event_frame_timestamps = timestamps

        backend = EventImuBackend()
        backend.run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))

        assert backend.diagnostics["corrected_pair_count"] == backend.diagnostics["event_pair_count"] - 1
        assert backend.diagnostics["invalid_pair_count"] == 1

    def test_missing_event_streams_raise_named_error(self):
        sequence = MvsecSequence(
            metadata=SequenceMetadata(source_path="unit", sequence_name="no_events"),
            diagnostics=LoadDiagnostics(),
            calibration=Calibration(),
            imu=_imu_at_rest(),
        )
        with pytest.raises(ValueError, match="event frames"):
            EventImuBackend().run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))


class TestDiagnostics:
    def test_run_result_exposes_pair_diagnostics(self):
        sequence = _static_scene_sequence()
        result = EventImuBackend().run_result(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))

        diagnostics = result.diagnostics
        assert diagnostics["event_pair_count"] == len(sequence.event_frame_timestamps) - 1
        assert diagnostics["corrected_pair_count"] > 0
        assert 0.0 < diagnostics["imu_samples_covered_fraction"] <= 1.0

    def test_focal_length_prefers_calibration(self):
        sequence = _static_scene_sequence()
        sequence.calibration.intrinsics_available = True
        sequence.calibration.data["K"] = np.array([[123.0, 0.0, 32.0], [0.0, 123.0, 32.0], [0.0, 0.0, 1.0]])

        backend = EventImuBackend()
        backend.run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))
        assert backend.diagnostics["focal_length_px"] == 123.0

        backend_override = EventImuBackend()
        backend_override.run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig(), focal_length_px=99.0))
        assert backend_override.diagnostics["focal_length_px"] == 99.0

    def test_invalid_calibration_falls_back_to_default_focal(self):
        sequence = _static_scene_sequence()
        sequence.calibration.data["K"] = np.zeros(9)

        backend = EventImuBackend()
        backend.run(sequence, config=EventImuConfig(imu_config=ImuOnlyConfig()))
        assert backend.diagnostics["focal_length_px"] == 200.0
