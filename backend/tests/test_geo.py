"""The brute-force Haversine formula used to check PostGIS (no database needed)."""

import math

import pytest

from app.services.geo import EARTH_RADIUS_M, haversine_m


def test_same_point_is_zero():
    assert haversine_m(26.9, 75.8, 26.9, 75.8) == 0


def test_one_degree_of_latitude():
    # On a sphere, one degree along a meridian is 2*pi*R/360.
    expected = 2 * math.pi * EARTH_RADIUS_M / 360

    assert haversine_m(0, 0, 1, 0) == pytest.approx(expected, abs=0.01)


def test_quarter_of_the_equator():
    expected = 2 * math.pi * EARTH_RADIUS_M / 4

    assert haversine_m(0, 0, 0, 90) == pytest.approx(expected, abs=0.01)


def test_distance_is_symmetric():
    a = haversine_m(26.91, 75.78, 26.85, 75.82)
    b = haversine_m(26.85, 75.82, 26.91, 75.78)

    assert a == pytest.approx(b)
