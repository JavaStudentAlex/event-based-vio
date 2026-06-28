"""Render synthetic events into inspectable frames and a preview video (Phase 6).

Events are accumulated into fixed time windows (``visualization_window_ms``). Positive events
render on the red channel and negative on the blue channel over a black background, so terrain
edges (roads, field boundaries, buildings) are visible in a moving sequence.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nav_benchmark.synthetic.config import EventCameraCfg
from nav_benchmark.synthetic.imageio import VideoBackendUnavailable, save_png_rgb, write_video
from nav_benchmark.synthetic.rgb_to_events import EventArrays


def render_event_frame(xs: np.ndarray, ys: np.ndarray, ps: np.ndarray, width: int, height: int) -> np.ndarray:
    """Accumulate a slice of events into an HxWx3 uint8 RGB image (pos=red, neg=blue)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    if xs.size:
        pos = ps > 0
        neg = ~pos
        frame[ys[pos], xs[pos], 0] = 255  # red for positive
        frame[ys[neg], xs[neg], 2] = 255  # blue for negative
    return frame


@dataclass
class EventFrames:
    frames: list[np.ndarray]
    window_times_s: list[float]


def build_event_frames(events: EventArrays, window_s: float) -> EventFrames:
    """Bin events into fixed windows from t=0 and render one image per window."""
    if window_s <= 0:
        raise ValueError("window_s must be > 0")
    frames: list[np.ndarray] = []
    times: list[float] = []
    if len(events) == 0:
        return EventFrames(frames=frames, window_times_s=times)

    t_max = float(events.t.max())
    n_windows = int(np.floor(t_max / window_s)) + 1
    bin_idx = np.floor(events.t / window_s).astype(np.int64)
    for w in range(n_windows):
        mask = bin_idx == w
        frame = render_event_frame(events.x[mask], events.y[mask], events.p[mask], events.width, events.height)
        frames.append(frame)
        times.append(w * window_s)
    return EventFrames(frames=frames, window_times_s=times)


def render(
    output_dir: str | Path,
    events: EventArrays,
    cfg: EventCameraCfg,
    preview_fps: float = 20.0,
    write_preview: bool = True,
    log=print,
) -> int:
    """Write ``events/event_frames/*.png`` and (best-effort) ``preview/events_preview.mp4``.

    Returns the number of event frames written.
    """
    output_dir = Path(output_dir)
    frames_dir = output_dir / "events" / "event_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    window_s = cfg.visualization_window_ms / 1000.0
    ef = build_event_frames(events, window_s)
    for i, frame in enumerate(ef.frames):
        save_png_rgb(frame, frames_dir / f"event_frame_{i:06d}.png")

    if write_preview and ef.frames:
        preview_path = output_dir / "preview" / "events_preview.mp4"
        try:
            write_video(ef.frames, preview_path, fps=preview_fps)
            log(f"Wrote {preview_path}")
        except VideoBackendUnavailable as exc:
            log(f"WARNING: skipping events preview mp4 ({exc})")

    return len(ef.frames)
