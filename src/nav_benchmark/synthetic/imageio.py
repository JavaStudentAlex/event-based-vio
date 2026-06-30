"""Headless-safe image and video IO.

PNG IO uses Pillow so the whole pipeline runs without OpenCV/libGL (the recorder's live
capture path lazy-imports OpenCV separately). Video writing is best-effort: it lazy-tries
OpenCV's ``VideoWriter`` and raises :class:`VideoBackendUnavailable` if no encoder is
present (e.g. no ffmpeg in CI), so callers can warn-and-skip instead of crashing.
"""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image


class VideoBackendUnavailable(RuntimeError):
    """Raised when no video encoder backend is available."""


def save_png_rgb(frame: np.ndarray, path: str | Path) -> None:
    """Save an HxWx3 uint8 RGB (or HxW grayscale) array as a PNG."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(frame)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    mode = "L" if arr.ndim == 2 else "RGB"
    Image.fromarray(arr, mode=mode).save(path)


def load_png_rgb(path: str | Path) -> np.ndarray:
    """Load a PNG as an HxWx3 uint8 RGB array."""
    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"), dtype=np.uint8)


def load_png_gray(path: str | Path) -> np.ndarray:
    """Load a PNG as an HxW uint8 grayscale array."""
    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.uint8)


def _require_video_frames(frames: Sequence[np.ndarray]) -> None:
    if not frames:
        raise ValueError("write_video requires at least one frame")


def _load_cv2_for_video():
    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise VideoBackendUnavailable(f"OpenCV not available for video writing: {exc}") from exc
    return cv2


def _video_writer(cv2, path: Path, fps: float, first_frame: np.ndarray):
    height, width = first_frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height))
    if not writer.isOpened():  # pragma: no cover - environment dependent
        raise VideoBackendUnavailable("OpenCV VideoWriter failed to open (missing codec/ffmpeg?)")
    return writer


def _write_video_frames(writer, frames: Sequence[np.ndarray]) -> None:
    for frame in frames:
        arr = np.asarray(frame)
        if arr.ndim == 2:
            arr = np.repeat(arr[:, :, None], 3, axis=2)
        writer.write(arr[:, :, ::-1].astype(np.uint8))


def write_video(frames: Sequence[np.ndarray], path: str | Path, fps: float) -> None:
    """Encode a sequence of RGB frames to an mp4 file (best-effort, via OpenCV).

    Raises :class:`VideoBackendUnavailable` if OpenCV/ffmpeg is not importable/usable.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _require_video_frames(frames)
    cv2 = _load_cv2_for_video()
    first = np.asarray(frames[0])
    writer = _video_writer(cv2, path, fps, first)
    try:
        _write_video_frames(writer, frames)
    finally:
        writer.release()
