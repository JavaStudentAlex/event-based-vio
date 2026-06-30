"""Frame sources for the recorder.

Two implementations share a small duck-typed interface (``start``, ``get_frame``, ``stop``,
``width``, ``height``):

- :class:`SyntheticFrameSource` renders a deterministic procedural "terrain" that translates
  and rotates with the drone state. It needs no Google Earth, OpenCV, or display, so the whole
  pipeline runs headless and produces non-zero events.
- :class:`GoogleEarthFrameSource` lazy-wraps the archive's ``FrameGrabber`` (+ ``KMLServer``)
  and is used once ``drone-ge-simulation-main`` and Google Earth Pro are available.
"""

from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image, ImageDraw

from nav_benchmark.synthetic.config import FlightCfg
from nav_benchmark.synthetic.geo import enu_from_geo


class FrameSource(Protocol):
    width: int
    height: int

    def start(self) -> None: ...

    def get_frame(self, state: dict[str, float]) -> np.ndarray:
        """Return the current view as an HxWx3 uint8 RGB array given the drone state."""
        ...

    def stop(self) -> None: ...


def _build_terrain_texture(size: int, seed: int) -> np.ndarray:
    """Procedurally build a high-contrast RGB terrain texture (deterministic given ``seed``)."""
    rng = np.random.RandomState(seed)
    img = Image.new("RGB", (size, size), color=(110, 120, 100))
    draw = ImageDraw.Draw(img)
    _draw_field_patches(draw, rng, size)
    _draw_road_grid(draw, size)
    _draw_buildings(draw, rng, size)
    _draw_trees(draw, rng, size)
    return np.asarray(img, dtype=np.uint8)


def _draw_field_patches(draw: ImageDraw.ImageDraw, rng: np.random.RandomState, size: int) -> None:
    for _ in range(40):
        x0, y0 = rng.randint(0, size, size=2)
        w, h = rng.randint(40, 200, size=2)
        color = tuple(int(c) for c in rng.randint(60, 180, size=3))
        draw.rectangle([x0, y0, x0 + w, y0 + h], fill=color)


def _draw_road_grid(draw: ImageDraw.ImageDraw, size: int) -> None:
    step = 64
    for x in range(0, size, step):
        draw.line([(x, 0), (x, size)], fill=(40, 40, 45), width=3)
    for y in range(0, size, step):
        draw.line([(0, y), (size, y)], fill=(40, 40, 45), width=3)


def _draw_buildings(draw: ImageDraw.ImageDraw, rng: np.random.RandomState, size: int) -> None:
    for _ in range(120):
        x0, y0 = rng.randint(0, size, size=2)
        s = rng.randint(6, 22)
        bright = tuple(int(c) for c in rng.randint(180, 255, size=3))
        draw.rectangle([x0, y0, x0 + s, y0 + s], fill=bright)


def _draw_trees(draw: ImageDraw.ImageDraw, rng: np.random.RandomState, size: int) -> None:
    for _ in range(160):
        x0, y0 = rng.randint(0, size, size=2)
        r = rng.randint(3, 10)
        draw.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=(30, 70, 40))


class SyntheticFrameSource:
    """Deterministic procedural frame source driven by the drone's ENU position and heading."""

    def __init__(
        self,
        width: int,
        height: int,
        flight: FlightCfg,
        seed: int = 42,
        pixels_per_meter: float = 4.0,
        texture_size: int = 1024,
    ) -> None:
        self.width = width
        self.height = height
        self._flight = flight
        self._ppm = pixels_per_meter
        self._lat0 = flight.start_lat
        self._lon0 = flight.start_lon
        self._alt0 = flight.start_alt_m
        self._texture = _build_terrain_texture(texture_size, seed)
        self._tex_h, self._tex_w = self._texture.shape[:2]

        # Output pixel grid, centered on the principal point.
        us, vs = np.meshgrid(np.arange(width), np.arange(height))
        self._du = (us - (width - 1) / 2.0).astype(np.float64)
        self._dv = (vs - (height - 1) / 2.0).astype(np.float64)

    def start(self) -> None:  # pragma: no cover - trivial
        pass

    def stop(self) -> None:  # pragma: no cover - trivial
        pass

    def get_frame(self, state: dict[str, float]) -> np.ndarray:
        e, n, _ = enu_from_geo(state["lat"], state["lon"], self._alt0, self._lat0, self._lon0, self._alt0)
        east = float(e)
        north = float(n)
        ang = np.radians(state["heading"])
        cos_a, sin_a = np.cos(ang), np.sin(ang)

        tex_cx = self._tex_w / 2.0 + east * self._ppm
        tex_cy = self._tex_h / 2.0 - north * self._ppm

        src_x = cos_a * self._du - sin_a * self._dv + tex_cx
        src_y = sin_a * self._du + cos_a * self._dv + tex_cy

        ix = np.mod(np.round(src_x).astype(np.int64), self._tex_w)
        iy = np.mod(np.round(src_y).astype(np.int64), self._tex_h)
        return self._texture[iy, ix]


class GoogleEarthFrameSource:
    """Wrap the archive ``FrameGrabber`` (and optional ``KMLServer``) for live capture.

    Lazy-imports the archive so importing this module never requires OpenCV or the archive.
    The recorder pushes deterministic state in via :meth:`get_frame`; if a ``KMLServer`` is
    supplied it is updated so Google Earth Pro follows that state.
    """

    def __init__(self, width: int, height: int, archive_dir: str | Path | None = None) -> None:
        self.width = width
        self.height = height
        self._archive_dir = Path(archive_dir) if archive_dir else None
        self._grabber: Any = None
        self._server: Any = None

    def _import_archive(self) -> Any:
        import importlib
        import sys

        if self._archive_dir and str(self._archive_dir) not in sys.path:
            sys.path.insert(0, str(self._archive_dir))
        return (
            importlib.import_module("capture"),
            importlib.import_module("server"),
        )

    def start(self) -> None:
        capture_mod, server_mod = self._import_archive()
        # Archive APIs are assumed; adapt these two lines when the archive lands.
        self._grabber = capture_mod.FrameGrabber()
        self._server = server_mod.KMLServer()
        _start_if_present(self._server)
        _start_if_present(self._grabber)

    def get_frame(self, state: dict[str, float]) -> np.ndarray:
        _update_server_state(self._server, state)
        return _frame_bgr_to_rgb(self._grabber.grab())

    def stop(self) -> None:
        for obj in (self._grabber, self._server):
            _stop_if_present(obj)


def _start_if_present(obj: Any) -> None:
    if hasattr(obj, "start"):
        obj.start()


def _stop_if_present(obj: Any) -> None:
    if obj is not None and hasattr(obj, "stop"):
        obj.stop()


def _update_server_state(server: Any, state: dict[str, float]) -> None:
    if server is not None and hasattr(server, "update_state"):
        server.update_state(state)


def _frame_bgr_to_rgb(frame_bgr: Any) -> np.ndarray:
    frame = np.asarray(frame_bgr, dtype=np.uint8)
    if frame.ndim == 3 and frame.shape[2] == 3:
        return frame[:, :, ::-1]
    return frame
