import numpy as np
import pytest

from nav_benchmark.trajectory.models import ExportMetadata, SyncDiagnostics, Trajectory


def test_trajectory_validation():
    # Valid
    Trajectory(
        timestamps=np.array([1.0]),
        method="test",
        positions=np.array([[1.0, 2.0, 3.0]]),
        orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )

    # Invalid positions shape
    with pytest.raises(ValueError, match="Positions must be shape"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0]]),
            orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
        )

    # Invalid orientations shape
    with pytest.raises(ValueError, match="Orientations must be shape"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0, 3.0]]),
            orientations=np.array([[0.0, 0.0, 1.0]]),
        )

    # Invalid velocities shape
    with pytest.raises(ValueError, match="Velocities must be shape"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0, 3.0]]),
            orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
            velocities=np.array([[1.0, 2.0]]),
        )

    # Invalid confidence shape
    with pytest.raises(ValueError, match="Confidence must be shape"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0, 3.0]]),
            orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
            confidence=np.array([1.0, 2.0]),
        )

    # Invalid health shape
    with pytest.raises(ValueError, match="Health must be shape"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0, 3.0]]),
            orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
            health=np.array(["OK", "OK"]),
        )

    # Invalid latency shape
    with pytest.raises(ValueError, match="Latency must be shape"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0, 3.0]]),
            orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
            latency_ms=np.array([10.0, 10.0]),
        )


def test_trajectory_invalid_health_values():
    with pytest.raises(ValueError, match="Invalid health value at index 0"):
        Trajectory(
            timestamps=np.array([1.0]),
            method="test",
            positions=np.array([[1.0, 2.0, 3.0]]),
            orientations=np.array([[0.0, 0.0, 0.0, 1.0]]),
            health=np.array(["UNKNOWN"]),
        )


def test_sync_diagnostics_validation():
    # Valid empty
    SyncDiagnostics(
        source_count=0,
        target_count=0,
        matched_count=0,
        unmatched_source_count=0,
        unmatched_target_count=0,
        tolerance_sec=0.1,
        first_matched_timestamp=None,
        last_matched_timestamp=None,
        overlap_sufficiency=0.0,
    )

    # Valid matched
    SyncDiagnostics(
        source_count=5,
        target_count=5,
        matched_count=3,
        unmatched_source_count=2,
        unmatched_target_count=2,
        tolerance_sec=0.1,
        first_matched_timestamp=1.0,
        last_matched_timestamp=3.0,
        overlap_sufficiency=0.6,
    )

    # Negative count values
    with pytest.raises(ValueError, match="source_count must be non-negative"):
        SyncDiagnostics(
            source_count=-1,
            target_count=0,
            matched_count=0,
            unmatched_source_count=0,
            unmatched_target_count=0,
            tolerance_sec=0.1,
            first_matched_timestamp=None,
            last_matched_timestamp=None,
            overlap_sufficiency=0.0,
        )

    # Sum mismatches
    with pytest.raises(ValueError, match=r"source_count must equal matched_count \+ unmatched_source_count"):
        SyncDiagnostics(
            source_count=5,
            target_count=5,
            matched_count=3,
            unmatched_source_count=1,  # should be 2
            unmatched_target_count=2,
            tolerance_sec=0.1,
            first_matched_timestamp=1.0,
            last_matched_timestamp=3.0,
            overlap_sufficiency=0.6,
        )

    # Overlap sufficiency out of bounds
    with pytest.raises(ValueError, match=r"overlap_sufficiency must be between 0\.0 and 1\.0"):
        SyncDiagnostics(
            source_count=5,
            target_count=5,
            matched_count=3,
            unmatched_source_count=2,
            unmatched_target_count=2,
            tolerance_sec=0.1,
            first_matched_timestamp=1.0,
            last_matched_timestamp=3.0,
            overlap_sufficiency=1.2,
        )

    # Match counts and timestamps consistency
    with pytest.raises(ValueError, match="first/last matched timestamps must be None when matched_count is 0"):
        SyncDiagnostics(
            source_count=5,
            target_count=5,
            matched_count=0,
            unmatched_source_count=5,
            unmatched_target_count=5,
            tolerance_sec=0.1,
            first_matched_timestamp=1.0,
            last_matched_timestamp=3.0,
            overlap_sufficiency=0.0,
        )

    with pytest.raises(ValueError, match="first/last matched timestamps must not be None when matched_count > 0"):
        SyncDiagnostics(
            source_count=5,
            target_count=5,
            matched_count=3,
            unmatched_source_count=2,
            unmatched_target_count=2,
            tolerance_sec=0.1,
            first_matched_timestamp=None,
            last_matched_timestamp=3.0,
            overlap_sufficiency=0.6,
        )

    with pytest.raises(ValueError, match="first_matched_timestamp must be <= last_matched_timestamp"):
        SyncDiagnostics(
            source_count=5,
            target_count=5,
            matched_count=3,
            unmatched_source_count=2,
            unmatched_target_count=2,
            tolerance_sec=0.1,
            first_matched_timestamp=3.0,
            last_matched_timestamp=1.0,
            overlap_sufficiency=0.6,
        )


def test_export_metadata_validation():
    # Valid
    ExportMetadata(
        timestamp_unit="seconds",
        association_policy="nearest_neighbor",
        association_tolerance_sec=0.05,
        source_frame="imu",
        target_frame="world",
        position_units="meters",
        orientation_format="quaternion_xyzw",
        health_counts={"OK": 5},
        tum_filtered_rows=0,
    )

    # Empty string validation
    with pytest.raises(ValueError, match="timestamp_unit must not be empty"):
        ExportMetadata(timestamp_unit="")

    # Negative tolerance
    with pytest.raises(ValueError, match="association_tolerance_sec must be non-negative"):
        ExportMetadata(association_tolerance_sec=-0.01)

    # Negative filtered rows
    with pytest.raises(ValueError, match="tum_filtered_rows must be non-negative"):
        ExportMetadata(tum_filtered_rows=-5)

    # Negative health count
    with pytest.raises(ValueError, match="health count for OK must be non-negative"):
        ExportMetadata(health_counts={"OK": -1})
