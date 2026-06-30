"""Preview artifacts for debugging/presentation (Phase 10).

All previews are derived, read-only with respect to raw data: the RGB preview may carry a
telemetry overlay (allowed for previews only) but never overwrites ``rgb/`` frames. The
trajectory plot uses matplotlib's Agg backend, so it works headless; the mp4 previews are
best-effort via :func:`nav_benchmark.synthetic.imageio.write_video`.
"""

import csv
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw

from nav_benchmark.synthetic.imageio import VideoBackendUnavailable, load_png_rgb, write_video

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _read_rgb_index(root: Path) -> list[tuple[float, Path]]:
    ts_csv = root / "metadata" / "rgb_timestamps.csv"
    if not ts_csv.exists():
        raise FileNotFoundError(f"rgb_timestamps.csv not found: {ts_csv}")
    out: list[tuple[float, Path]] = []
    with open(ts_csv, newline="") as f:
        for row in csv.DictReader(f):
            out.append((float(row["timestamp_s"]), root / row["path"]))
    return out


def _load_raw_states(root: Path) -> np.ndarray | None:
    state_path = root / "metadata" / "raw_state_log.csv"
    if not state_path.exists():
        return None
    return np.loadtxt(state_path, delimiter=",", skiprows=1, ndmin=2)


def _overlay_rgb_telemetry(img: Image.Image, timestamp: float, state_row: np.ndarray) -> None:
    _, _, _, alt, heading, speed = state_row
    draw = ImageDraw.Draw(img)
    draw.text(
        (6, 6),
        f"t={timestamp:6.2f}s hdg={heading:6.1f} v={speed:4.1f} alt={alt:6.1f}",
        fill=(255, 255, 0),
    )


def _rgb_preview_frames(root: Path, overlay: bool) -> list[np.ndarray]:
    states = _load_raw_states(root)
    frames: list[np.ndarray] = []
    for i, (timestamp, path) in enumerate(_read_rgb_index(root)):
        img = Image.fromarray(load_png_rgb(path))
        if overlay and states is not None and i < states.shape[0]:
            _overlay_rgb_telemetry(img, timestamp, states[i])
        frames.append(np.asarray(img, dtype=np.uint8))
    return frames


def _write_preview_video(frames: list[np.ndarray], out: Path, fps: float, label: str, log) -> bool:
    try:
        write_video(frames, out, fps=fps)
        log(f"Wrote {out}")
        return True
    except (VideoBackendUnavailable, ValueError) as exc:
        log(f"WARNING: skipping {label} preview mp4 ({exc})")
        return False


def write_rgb_preview(root: str | Path, fps: float = 30.0, overlay: bool = True, log=print) -> bool:
    """Write ``preview/rgb_preview.mp4`` from saved RGB frames. Returns True if written."""
    root = Path(root)
    return _write_preview_video(
        _rgb_preview_frames(root, overlay), root / "preview" / "rgb_preview.mp4", fps, "rgb", log
    )


def write_events_preview_from_frames(root: str | Path, fps: float = 20.0, log=print) -> bool:
    """Write ``preview/events_preview.mp4`` from existing ``events/event_frames/*.png``."""
    root = Path(root)
    frame_paths = sorted((root / "events" / "event_frames").glob("event_frame_*.png"))
    if not frame_paths:
        log("WARNING: no event frames found for events preview")
        return False
    frames = [load_png_rgb(p) for p in frame_paths]
    return _write_preview_video(frames, root / "preview" / "events_preview.mp4", fps, "events", log)


def write_trajectory_preview(root: str | Path, log=print) -> bool:
    """Plot the local ENU trajectory to ``preview/trajectory_preview.png`` (always works headless)."""
    root = Path(root)
    traj_path = root / "ground_truth" / "trajectory.csv"
    if not traj_path.exists():
        raise FileNotFoundError(f"trajectory.csv not found: {traj_path}")
    data = np.loadtxt(traj_path, delimiter=",", skiprows=1, ndmin=2)
    x, y = data[:, 1], data[:, 2]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(x, y, "-", color="steelblue", linewidth=1.5, label="trajectory")
    ax.plot(x[0], y[0], "o", color="green", markersize=9, label="start")
    ax.plot(x[-1], y[-1], "s", color="red", markersize=9, label="end")
    _draw_heading_arrows(ax, data)
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.set_title("Local ENU trajectory")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    out = root / "preview" / "trajectory_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    log(f"Wrote {out}")
    return True


def _draw_heading_arrows(ax, data: np.ndarray, n_arrows: int = 12) -> None:
    x, y, yaw_deg = data[:, 1], data[:, 2], data[:, 4]
    if x.size < 2:
        return
    idx = np.linspace(0, x.size - 1, min(n_arrows, x.size)).astype(int)
    yaw = np.radians(yaw_deg[idx])
    # Heading 0 = north (+y), 90 = east (+x).
    u, v = np.sin(yaw), np.cos(yaw)
    ax.quiver(x[idx], y[idx], u, v, color="darkorange", scale=25, width=0.004, alpha=0.7)
