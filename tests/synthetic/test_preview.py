import numpy as np

from nav_benchmark.synthetic import preview


def test_write_rgb_preview_uses_frames_and_overlay(mutable_sequence, monkeypatch):
    calls = []

    def fake_write_video(frames, out, fps):
        calls.append((frames, out, fps))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake video")

    monkeypatch.setattr(preview, "write_video", fake_write_video)

    messages = []
    assert preview.write_rgb_preview(mutable_sequence, fps=12.0, overlay=True, log=messages.append)

    frames, out, fps = calls[0]
    assert out == mutable_sequence / "preview" / "rgb_preview.mp4"
    assert fps == 12.0
    assert len(frames) > 0
    assert all(frame.dtype == np.uint8 for frame in frames)
    assert (mutable_sequence / "preview" / "rgb_preview.mp4").read_bytes() == b"fake video"
    assert messages == [f"Wrote {out}"]


def test_write_events_preview_from_frames(mutable_sequence, monkeypatch):
    calls = []

    def fake_write_video(frames, out, fps):
        calls.append((frames, out, fps))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake event video")

    monkeypatch.setattr(preview, "write_video", fake_write_video)

    messages = []
    assert preview.write_events_preview_from_frames(mutable_sequence, fps=9.0, log=messages.append)

    frames, out, fps = calls[0]
    assert out == mutable_sequence / "preview" / "events_preview.mp4"
    assert fps == 9.0
    assert len(frames) > 0
    assert (mutable_sequence / "preview" / "events_preview.mp4").read_bytes() == b"fake event video"
    assert messages == [f"Wrote {out}"]


def test_write_events_preview_warns_without_frames(tmp_path):
    messages = []

    assert not preview.write_events_preview_from_frames(tmp_path, log=messages.append)
    assert messages == ["WARNING: no event frames found for events preview"]
