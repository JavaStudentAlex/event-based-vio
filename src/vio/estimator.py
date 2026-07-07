from dataclasses import dataclass
from typing import Iterable, Tuple

from .event_processor import EventPacket, EventProcessor
from .imu_processor import IMUSample, IMUProcessor


@dataclass
class EstimatorState:
    t: float
    qx: float
    qy: float
    qz: float
    qw: float


class Estimator:
    """
    Minimal estimator that ties EventProcessor + IMUProcessor together.

    This is a stub to satisfy S02/T03 wiring and artifact-shape checks.
    """

    def __init__(self, width: int, height: int):
        self.events = EventProcessor(width, height)
        self.imu = IMUProcessor()
        self.t: float = 0.0

    def step(self, event_packets: Iterable[EventPacket], imu_samples: Iterable[IMUSample]) -> EstimatorState:
        # Normalize event packets (no-op aside from clamping)
        _ = self.events.normalize(event_packets)
        qx, qy, qz, qw = self.imu.step(imu_samples)
        return EstimatorState(t=self.t, qx=qx, qy=qy, qz=qz, qw=qw)
