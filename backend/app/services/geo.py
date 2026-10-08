"""Small geography helpers.

All distances in this project are STRAIGHT-LINE ("as the crow flies") approximations.
Real travel distance by road is always longer.
"""

import math

from geoalchemy2 import Geography
from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius in metres (IUGG value)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points on a sphere, in metres.

    Used in tests as an independent, brute-force check of the PostGIS results.
    PostGIS measures on the WGS84 ellipsoid, so the two can differ by up to about 0.56%.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def geography_point(lat: float, lon: float) -> ColumnElement:
    """SQL expression for a geography point. Note PostGIS wants (longitude, latitude)."""
    return func.geography(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), type_=Geography)
