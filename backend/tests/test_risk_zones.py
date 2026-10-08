"""Risk zones: the GeoJSON map endpoint and seeding from a JSON file."""

import json

from sqlalchemy import func, select

from app.core.config import REPO_ROOT
from app.models.risk import RiskLevel, RiskZone
from app.models.user import Role
from app.services.zones import seed_zones
from tests.conftest import auth_headers
from tests.test_geofence import add_zone

BBOX_AROUND_TEST_ZONE = "11.9,11.9,12.1,12.1"


def test_bbox_returns_geojson_for_overlapping_zones(client, db, users):
    zone = add_zone(db, "Test map zone", RiskLevel.HIGH)
    add_zone(db, "Test far zone", RiskLevel.LOW, lat=14.0, lon=14.0)
    db.commit()
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.get(f"/risk-zone?bbox={BBOX_AROUND_TEST_ZONE}", headers=headers).json()

    assert body["type"] == "FeatureCollection"
    assert [f["properties"]["id"] for f in body["features"]] == [zone.id]
    feature = body["features"][0]
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["level"] == "HIGH"
    assert feature["properties"]["is_synthetic"] is True
    assert "not predictions" in body["note"]


def test_bad_bbox_is_rejected(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    for bad in ["1,2,3", "a,b,c,d", "12,12,11,11", "0,0,50,50"]:
        assert client.get(f"/risk-zone?bbox={bad}", headers=headers).status_code == 422


def test_risk_zone_needs_login(client):
    assert client.get(f"/risk-zone?bbox={BBOX_AROUND_TEST_ZONE}").status_code == 401


def test_seed_file_is_labelled_synthetic():
    data = json.loads((REPO_ROOT / "ml" / "data" / "synthetic_risk_zones_jaipur.json").read_text())

    assert "SYNTHETIC" in data["_note"]
    assert all(zone["level"] in RiskLevel.__members__ for zone in data["zones"])


def test_seeding_twice_updates_instead_of_duplicating(db, tmp_path):
    spec = {
        "source": "synthetic-seed",
        "zones": [
            {"name": "Seed test zone", "lat": 13.0, "lon": 13.0, "radius_m": 250, "level": "LOW"}
        ],
    }
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(spec))

    first = seed_zones(db, path)
    spec["zones"][0]["level"] = "CRITICAL"
    path.write_text(json.dumps(spec))
    second = seed_zones(db, path)

    assert (first, second) == ((1, 0), (0, 1))
    zone = db.scalar(select(RiskZone).where(RiskZone.name == "Seed test zone"))
    assert zone.base_level == RiskLevel.CRITICAL
    # The 250 m circle has an area of about pi * 250^2 = 196,350 m^2 (within 1%).
    area = db.scalar(
        select(func.ST_Area(func.geography(RiskZone.geom))).where(RiskZone.id == zone.id)
    )
    assert abs(area - 196_350) / 196_350 < 0.01
