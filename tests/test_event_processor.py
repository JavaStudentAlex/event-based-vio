from src.vio.event_processor import EventPacket, EventProcessor


def test_event_processor_clamps_and_normalizes():
    proc = EventProcessor(width=4, height=3)
    pkt = EventPacket(t=1.0, x=[-1, 0, 3, 99], y=[0, -5, 2, 100], p=[-1, 0, 1, 2])

    out = proc.normalize([pkt])
    assert len(out) == 1
    o = out[0]
    # x clamped into [0, width-1] = [0,3]
    assert o.x == [0, 0, 3, 3]
    # y clamped into [0, height-1] = [0,2]
    assert o.y == [0, 0, 2, 2]
    # polarity normalized to 0/1
    assert o.p == [0, 0, 1, 1]
    # timestamp preserved
    assert o.t == 1.0
