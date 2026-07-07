from collections.abc import Iterable
from dataclasses import dataclass

from .event_processor import EventPacket, EventProcessor
from .imu_processor import IMUProcessor, IMUSample


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
        # Convert to lists to allow multiple passes / safe iteration
        event_list = list(event_packets)
        imu_list = list(imu_samples)

        # Normalize event packets
        _ = self.events.normalize(event_list)
        qx, qy, qz, qw = self.imu.step(imu_list)

        # Update current estimator timestamp to the latest timestamp among processed inputs
        ts = []
        for p in event_list:
            ts.append(p.t)
        for s in imu_list:
            ts.append(s.t)
        if ts:
            self.t = max(ts)

        return EstimatorState(t=self.t, qx=qx, qy=qy, qz=qz, qw=qw)
