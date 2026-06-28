from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.export import PROJECT_TRAJECTORY_COLUMNS
from nav_benchmark.trajectory.models import Trajectory


@dataclass(frozen=True)
class EstimatorDescriptor:
    """Static metadata used by the runner and evaluator to keep baselines comparable."""

    method: str
    required_streams: tuple[str, ...] = ()
    output_columns: tuple[str, ...] = tuple(PROJECT_TRAJECTORY_COLUMNS)


@dataclass
class EstimatorRunResult:
    """Standard result envelope returned by all estimator backends."""

    trajectory: Trajectory
    config: Any = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


class BaseOdometryBackend(ABC):
    """
    Abstract base class for visual-inertial odometry backends.
    """

    method: ClassVar[str] = "unknown"
    required_streams: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def describe(cls) -> EstimatorDescriptor:
        """Return the estimator contract advertised by this backend."""
        return EstimatorDescriptor(method=cls.method, required_streams=cls.required_streams)

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

    def run_result(self, sequence: MvsecSequence, *, config: Any = None) -> EstimatorRunResult:
        """Run the backend and wrap its trajectory in the common result envelope."""
        trajectory = self.run(sequence, config=config)
        self.validate_output(trajectory)
        return EstimatorRunResult(trajectory=trajectory, config=config)

    def validate_output(self, trajectory: Trajectory) -> None:
        """Validate the invariant that backend output can be exported and evaluated."""
        descriptor = self.describe()
        if descriptor.method != "unknown" and trajectory.method != descriptor.method:
            raise ValueError(f"Estimator {descriptor.method!r} returned trajectory method {trajectory.method!r}")
