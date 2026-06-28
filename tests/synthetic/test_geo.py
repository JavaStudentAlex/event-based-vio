import numpy as np

from nav_benchmark.synthetic.geo import enu_from_geo, geo_from_enu

LAT0, LON0, ALT0 = 50.4501, 30.5234, 100.0


def test_origin_maps_to_zero():
    e, n, _ = enu_from_geo(LAT0, LON0, ALT0, LAT0, LON0, ALT0)
    assert float(e) == 0.0
    assert float(n) == 0.0


def test_east_displacement_is_positive_for_longitude_increase():
    e, n, _ = enu_from_geo(LAT0, LON0 + 0.001, ALT0, LAT0, LON0, ALT0)
    assert float(e) > 0.0
    assert abs(float(n)) < 1e-6


def test_north_displacement_is_positive_for_latitude_increase():
    e, n, _ = enu_from_geo(LAT0 + 0.001, LON0, ALT0, LAT0, LON0, ALT0)
    assert float(n) > 0.0
    assert abs(float(e)) < 1e-6


def test_outputs_are_finite_and_z_is_absolute_altitude():
    lat = np.array([LAT0, LAT0 + 0.01, LAT0 - 0.01])
    lon = np.array([LON0, LON0 + 0.01, LON0 - 0.02])
    alt = np.array([100.0, 110.0, 90.0])
    e, n, u = enu_from_geo(lat, lon, alt, LAT0, LON0, ALT0)
    assert np.all(np.isfinite(e)) and np.all(np.isfinite(n)) and np.all(np.isfinite(u))
    assert np.allclose(u, alt)  # up is absolute altitude


def test_round_trip_enu_geo():
    lat = np.array([LAT0 + 0.002, LAT0 - 0.003])
    lon = np.array([LON0 - 0.004, LON0 + 0.005])
    alt = np.array([100.0, 100.0])
    e, n, u = enu_from_geo(lat, lon, alt, LAT0, LON0, ALT0)
    lat2, lon2, alt2 = geo_from_enu(e, n, u, LAT0, LON0, ALT0)
    assert np.allclose(lat, lat2, atol=1e-9)
    assert np.allclose(lon, lon2, atol=1e-9)
    assert np.allclose(alt, alt2)
