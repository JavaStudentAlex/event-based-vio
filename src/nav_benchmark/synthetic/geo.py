"""Geodetic -> local metric conversion.

For the short flights produced by this pipeline an equirectangular approximation around
the first GPS fix is sufficient. The local frame is East-North-Up (ENU):

    x = east_m   (increases with longitude east of the origin)
    y = north_m  (increases with latitude north of the origin)
    z = altitude_m (absolute altitude, not origin-relative)

Heading is a compass bearing in degrees (0 = North, 90 = East), used directly as yaw.
"""

import numpy as np

EARTH_RADIUS_M = 6371000.0


def enu_from_geo(
    lat: np.ndarray | float,
    lon: np.ndarray | float,
    alt: np.ndarray | float,
    lat0: float,
    lon0: float,
    alt0: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert latitude/longitude/altitude to local ENU meters about ``(lat0, lon0, alt0)``.

    ``alt0`` is accepted for API symmetry and origin bookkeeping but the returned ``up``
    is absolute altitude (``z = alt``) to match the trajectory schema.

    Returns ``(east_m, north_m, up_m)`` as arrays (scalars are broadcast to 0-d arrays).
    """
    lat_arr = np.asarray(lat, dtype=np.float64)
    lon_arr = np.asarray(lon, dtype=np.float64)
    alt_arr = np.asarray(alt, dtype=np.float64)

    lat0_rad = np.radians(lat0)
    east = np.radians(lon_arr - lon0) * EARTH_RADIUS_M * np.cos(lat0_rad)
    north = np.radians(lat_arr - lat0) * EARTH_RADIUS_M
    up = alt_arr
    # Broadcast up to the shape of the horizontal components when alt is scalar.
    up = np.broadcast_to(up, east.shape).astype(np.float64)
    return east, north, up


def geo_from_enu(
    east: np.ndarray | float,
    north: np.ndarray | float,
    up: np.ndarray | float,
    lat0: float,
    lon0: float,
    alt0: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Inverse of :func:`enu_from_geo` (useful for tests and round-tripping)."""
    east_arr = np.asarray(east, dtype=np.float64)
    north_arr = np.asarray(north, dtype=np.float64)
    up_arr = np.asarray(up, dtype=np.float64)

    lat0_rad = np.radians(lat0)
    lat = lat0 + np.degrees(north_arr / EARTH_RADIUS_M)
    lon = lon0 + np.degrees(east_arr / (EARTH_RADIUS_M * np.cos(lat0_rad)))
    alt = up_arr
    return lat, lon, alt
