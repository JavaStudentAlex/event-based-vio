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


def write_rgb_preview(root: str | Path, fps: float = 30.0, overlay: bool = True, log=print) -> bool:
    """Write ``preview/rgb_preview.mp4`` from saved RGB frames. Returns True if written."""
    root = Path(root)
    frames_index = _read_rgb_index(root)
    state_path = root / "metadata" / "raw_state_log.csv"
    states = np.loadtxt(state_path, delimiter=",", skiprows=1, ndmin=2) if state_path.exists() else None

    frames: list[np.ndarray] = []
    for i, (t, path) in enumerate(frames_index):
        img = Image.fromarray(load_png_rgb(path))
        if overlay and states is not None and i < states.shape[0]:
            _, _, _, alt, heading, speed = states[i]
            draw = ImageDraw.Draw(img)
            draw.text((6, 6), f"t={t:6.2f}s hdg={heading:6.1f} v={speed:4.1f} alt={alt:6.1f}", fill=(255, 255, 0))
        frames.append(np.asarray(img, dtype=np.uint8))

    out = root / "preview" / "rgb_preview.mp4"
    try:
        write_video(frames, out, fps=fps)
        log(f"Wrote {out}")
        return True
    except (VideoBackendUnavailable, ValueError) as exc:
        log(f"WARNING: skipping rgb preview mp4 ({exc})")
        return False


def write_events_preview_from_frames(root: str | Path, fps: float = 20.0, log=print) -> bool:
    """Write ``preview/events_preview.mp4`` from existing ``events/event_frames/*.png``."""
    root = Path(root)
    frame_paths = sorted((root / "events" / "event_frames").glob("event_frame_*.png"))
    if not frame_paths:
        log("WARNING: no event frames found for events preview")
        return False
    frames = [load_png_rgb(p) for p in frame_paths]
    out = root / "preview" / "events_preview.mp4"
    try:
        write_video(frames, out, fps=fps)
        log(f"Wrote {out}")
        return True
    except (VideoBackendUnavailable, ValueError) as exc:
        log(f"WARNING: skipping events preview mp4 ({exc})")
        return False


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
