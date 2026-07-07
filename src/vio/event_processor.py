from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class EventPacket:
    """
    Minimal event packet representation for schema validation across methods.

    Attributes
    ----------
    t: float
        Packet timestamp in seconds.
    x: List[int]
        X coordinates of events in pixel units.
    y: List[int]
        Y coordinates of events in pixel units.
    p: List[int]
        Polarity bits (0/1) for each event.
    """

    t: float
    x: list[int]
    y: list[int]
    p: list[int]


class EventProcessor:
    """
    Deterministic event preprocessor stub.

    Goal for S02: provide a stable interface and shape so downstream
    artifact schema checks can compare outputs across methods.
    """

    def __init__(self, width: int, height: int):
        self.width = int(width)
        self.height = int(height)

    def normalize(self, packets: Iterable[EventPacket]) -> list[EventPacket]:
        """
        Return packets with x/y clamped to the valid image range.
        No filtering, no resampling; stable/deterministic.
        """
        out: list[EventPacket] = []
        for pkt in packets:
            xs = [min(self.width - 1, max(0, int(v))) for v in pkt.x]
            ys = [min(self.height - 1, max(0, int(v))) for v in pkt.y]
            # Polarity normalized to 0/1 with negatives treated as 0
            ps = [1 if int(b) > 0 else 0 for b in pkt.p]
            out.append(EventPacket(t=float(pkt.t), x=xs, y=ys, p=ps))
        return out
