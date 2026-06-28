from abc import ABC, abstractmethod
from typing import Any

from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import Trajectory


class BaseOdometryBackend(ABC):
    """
    Abstract base class for visual-inertial odometry backends.
    """

    @abstractmethod
    def run(self, sequence: MvsecSequence, *, config: Any = None) -> Trajectory:
        """
        Runs the odometry estimator on the sequence.

        Args:
            sequence: The input MvsecSequence containing IMU, image, event, etc. streams.
            config: Optional backend-specific configuration object.

        Returns:
            A Trajectory object containing the estimated states.
        """
        pass
