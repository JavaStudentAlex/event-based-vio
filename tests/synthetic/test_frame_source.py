import sys

import numpy as np

from nav_benchmark.synthetic.frame_source import GoogleEarthFrameSource


def test_google_earth_frame_source_uses_archive_modules(tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, "capture", raising=False)
    monkeypatch.delitem(sys.modules, "server", raising=False)
    (tmp_path / "capture.py").write_text(
        """
import numpy as np

class FrameGrabber:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def grab(self):
        return np.array([[[1, 2, 3]]], dtype=np.uint8)
""",
        encoding="utf-8",
    )
    (tmp_path / "server.py").write_text(
        """
class KMLServer:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.state = None

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def update_state(self, state):
        self.state = state
""",
        encoding="utf-8",
    )

    source = GoogleEarthFrameSource(width=1, height=1, archive_dir=tmp_path)
    source.start()
    state = {"lat": 1.0, "lon": 2.0, "heading": 90.0}
    frame = source.get_frame(state)
    source.stop()

    assert source._grabber.started
    assert source._grabber.stopped
    assert source._server.started
    assert source._server.stopped
    assert source._server.state == state
    np.testing.assert_array_equal(frame, np.array([[[3, 2, 1]]], dtype=np.uint8))
