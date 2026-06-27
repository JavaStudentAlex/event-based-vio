import numpy as np
import pytest

from nav_benchmark.trajectory.models import Trajectory


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
