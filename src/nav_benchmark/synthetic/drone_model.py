"""Deterministic kinematic drone model (Phase 2).

The archive's ``DroneController`` changes heading randomly, which is fine for a visual demo
but bad for reproducible benchmarks. This pure-Python controller is fully deterministic: it
integrates a constant-speed flight whose heading follows a time-indexed ``heading_script``.

It is both the deterministic drone *and* the ground-truth source. Position is integrated in
the local ENU frame and converted back to lat/lon with the same equirectangular origin used
by :mod:`nav_benchmark.synthetic.geo`, so ``enu_from_geo`` recovers the integrated path exactly.
"""

import math
from dataclasses import dataclass

from nav_benchmark.synthetic.config import FlightCfg
from nav_benchmark.synthetic.geo import geo_from_enu


@dataclass
class HeadingScript:
    """Piecewise-linear heading-vs-time schedule (degrees).

    Heading is linearly interpolated between keyframes and held constant before the first
    and after the last keyframe. Equal consecutive keyframes (and the held tail) are straight
    segments; differing keyframes are smooth turns with constant yaw rate.
    """

    times_s: list[float]
    headings_deg: list[float]

    @classmethod
    def from_config(cls, flight: FlightCfg) -> "HeadingScript":
        if flight.deterministic_heading and flight.heading_script:
            times = [p.t_s for p in flight.heading_script]
            headings = [p.heading_deg for p in flight.heading_script]
        else:
            times = [0.0]
            headings = [flight.start_heading_deg]
        return cls(times_s=times, headings_deg=headings)

    def heading_at(self, t_s: float) -> float:
        times = self.times_s
        headings = self.headings_deg
        if t_s <= times[0]:
            return headings[0]
        if t_s >= times[-1]:
            return headings[-1]
        return _interpolated_heading(t_s, times, headings)


def _interpolated_heading(t_s: float, times: list[float], headings: list[float]) -> float:
    index = _heading_segment_index(t_s, times)
    t0, t1 = times[index - 1], times[index]
    h0, h1 = headings[index - 1], headings[index]
    frac = (t_s - t0) / (t1 - t0) if t1 > t0 else 0.0
    return h0 + frac * (h1 - h0)


def _heading_segment_index(t_s: float, times: list[float]) -> int:
    for i in range(1, len(times)):
        if t_s <= times[i]:
            return i
    return len(times) - 1


class KinematicDroneController:
    """Deterministic constant-speed drone driven by a :class:`HeadingScript`.

    Compatible with the archive's interface via :meth:`get_state`, which returns
    ``{"lat", "lon", "alt", "heading", "speed"}``.
    """

    def __init__(self, flight: FlightCfg, random_seed: int = 42) -> None:
        self._flight = flight
        self._random_seed = random_seed  # reserved for optional future jitter
        self._script = HeadingScript.from_config(flight)

        self._lat0 = flight.start_lat
        self._lon0 = flight.start_lon
        self._alt0 = flight.start_alt_m
        self._speed = flight.speed_mps

        self._t = 0.0
        self._east = 0.0
        self._north = 0.0
        self._heading = self._script.heading_at(0.0)
        self._lat = flight.start_lat
        self._lon = flight.start_lon

    @property
    def heading(self) -> float:
        return self._heading

    def update_to(self, t_s: float) -> None:
        """Advance the integrated state to absolute time ``t_s`` (>= current time)."""
        if t_s < self._t:
            raise ValueError(f"update_to went backwards: {t_s} < {self._t}")
        dt = t_s - self._t
        if dt > 0.0:
            heading_rad = math.radians(self._heading)
            self._east += self._speed * math.sin(heading_rad) * dt
            self._north += self._speed * math.cos(heading_rad) * dt
            lat, lon, _ = geo_from_enu(self._east, self._north, self._alt0, self._lat0, self._lon0, self._alt0)
            self._lat = float(lat)
            self._lon = float(lon)
            self._t = t_s
        # Heading applies to the *next* integration step (sampled at the new time).
        self._heading = self._script.heading_at(t_s)

    def get_state(self) -> dict[str, float]:
        return {
            "lat": self._lat,
            "lon": self._lon,
            "alt": self._alt0,
            "heading": self._heading,
            "speed": self._speed,
        }
