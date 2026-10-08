"""Nearest-resource search (cross-checked against brute-force Haversine), recommendations,
and SIMULATED assignment.

Test resources use far-away coordinates (around 10 N, 10 E, in open land) so they never mix
with real OpenStreetMap resources that may already be imported into the database.
"""

import random

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.resource import (
    AssignmentStatus,
    Availability,
    ResourceType,
    ResponseAssignment,
    ResponseResource,
)
from app.models.user import Role
from app.services.geo import haversine_m
from tests.conftest import auth_headers

CENTER_LAT, CENTER_LON = 10.0, 10.0
SEED = 20251008
# Haversine uses a sphere, PostGIS the WGS84 ellipsoid: they differ by up to about 0.56%.
RELATIVE_TOLERANCE = 0.006


def add_resource(
    db,
    name: str,
    lat: float,
    lon: float,
    resource_type: ResourceType = ResourceType.POLICE_STATION,
    availability: Availability = Availability.AVAILABLE,
    capabilities: list[str] | None = None,
) -> ResponseResource:
    resource = ResponseResource(
        name=name,
        resource_type=resource_type,
        geog=WKTElement(f"POINT({lon} {lat})", srid=4326),
        source="manual",
        capabilities=capabilities or [],
        availability_sim=availability,
    )
    db.add(resource)
    db.flush()
    return resource


@pytest.fixture
def random_resources(db):
    """60 resources at seeded random spots within about 30 km of the centre."""
    rng = random.Random(SEED)
    resources = []
    for i in range(60):
        lat = CENTER_LAT + rng.uniform(-0.25, 0.25)
        lon = CENTER_LON + rng.uniform(-0.25, 0.25)
        resource_type = rng.choice(list(ResourceType))
        resources.append((add_resource(db, f"R{i}", lat, lon, resource_type), lat, lon))
    db.commit()
    return resources


def brute_force_nearest(resources, lat, lon, types=None):
    """Measure the distance to EVERY resource and sort: slow but obviously correct."""
    rows = [
        (haversine_m(lat, lon, r_lat, r_lon), resource.id)
        for resource, r_lat, r_lon in resources
        if types is None or resource.resource_type in types
    ]
    return sorted(rows)


def assert_matches_brute_force(api_rows, expected, k):
    assert len(api_rows) == k
    expected_ids = [rid for _, rid in expected[:k]]
    expected_distance = dict((rid, d) for d, rid in expected)
    for row in api_rows:
        assert row["distance_kind"] == "straight_line"
        assert row["distance_m"] == pytest.approx(
            expected_distance[row["id"]], rel=RELATIVE_TOLERANCE
        )
    if [row["id"] for row in api_rows] != expected_ids:
        # Only acceptable if the differing items are near-ties (within the tolerance).
        for row, (exp_d, _) in zip(api_rows, expected[:k], strict=True):
            assert row["distance_m"] == pytest.approx(exp_d, rel=2 * RELATIVE_TOLERANCE)


@pytest.mark.parametrize("k", [1, 5, 10])
def test_nearest_matches_haversine_brute_force(client, users, random_resources, k):
    headers = auth_headers(client, users[Role.OPERATOR])
    query_lat, query_lon = CENTER_LAT + 0.03, CENTER_LON - 0.04

    rows = client.get(
        f"/nearby-resources?lat={query_lat}&lon={query_lon}&k={k}", headers=headers
    ).json()

    expected = brute_force_nearest(random_resources, query_lat, query_lon)
    assert_matches_brute_force(rows, expected, k)


def test_type_filter_matches_haversine_brute_force(client, users, random_resources):
    headers = auth_headers(client, users[Role.OPERATOR])

    rows = client.get(
        f"/nearby-resources?lat={CENTER_LAT}&lon={CENTER_LON}&type=hospital&k=5", headers=headers
    ).json()

    assert {row["resource_type"] for row in rows} == {"hospital"}
    expected = brute_force_nearest(
        random_resources, CENTER_LAT, CENTER_LON, types={ResourceType.HOSPITAL}
    )
    assert_matches_brute_force(rows, expected, 5)


def test_nearby_validates_coordinates_and_needs_login(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    assert client.get("/nearby-resources?lat=95&lon=10", headers=headers).status_code == 422
    assert client.get("/nearby-resources?lat=10&lon=10").status_code == 401


# ---------- recommendations and simulated assignment ----------


def _incident_with_location(client, users, category_code, lat=CENTER_LAT, lon=CENTER_LON):
    tourist = auth_headers(client, users[Role.TOURIST])
    client.put("/tourist/consent", headers=tourist, json={"location_consent": True})
    body = {
        "description": "Test incident for resource ranking",
        "category_code": category_code,
        "location": {"lat": lat, "lon": lon, "accuracy_m": 10},
    }
    return client.post("/incidents", headers=tourist, json=body).json()["id"]


def _acknowledge(client, headers, incident_id):
    client.patch(
        f"/incidents/{incident_id}/status", headers=headers, json={"status": "ACKNOWLEDGED"}
    )


def test_recommendations_follow_department_availability_and_distance(client, db, users):
    near_busy = add_resource(db, "Near busy", 10.001, 10.0, availability=Availability.BUSY)
    mid_free = add_resource(db, "Mid free", 10.01, 10.0)
    far_free = add_resource(db, "Far free", 10.05, 10.0)
    offline = add_resource(db, "Offline", 10.0005, 10.0, availability=Availability.OFFLINE)
    add_resource(db, "Hospital", 10.0002, 10.0, resource_type=ResourceType.HOSPITAL)
    db.commit()
    incident_id = _incident_with_location(client, users, "theft")  # Police department
    headers = auth_headers(client, users[Role.OPERATOR])

    rows = client.get(f"/incidents/{incident_id}/recommended-resources?k=3", headers=headers).json()

    assert [r["id"] for r in rows] == [mid_free.id, far_free.id, near_busy.id]
    assert offline.id not in [r["id"] for r in rows]
    assert {r["resource_type"] for r in rows} == {"police_station"}


def test_far_away_available_resource_is_not_recommended(client, db, users):
    # Regression test: an AVAILABLE station ~55 km away must not beat a BUSY one nearby.
    near_busy = add_resource(db, "Near busy", 10.001, 10.0, availability=Availability.BUSY)
    far_free = add_resource(db, "Far free", 10.5, 10.0)  # beyond the 25 km radius
    db.commit()
    incident_id = _incident_with_location(client, users, "theft")
    headers = auth_headers(client, users[Role.OPERATOR])

    rows = client.get(f"/incidents/{incident_id}/recommended-resources?k=3", headers=headers).json()

    assert [r["id"] for r in rows] == [near_busy.id]
    assert far_free.id not in [r["id"] for r in rows]


def test_medical_prefers_hospital_with_emergency_department(client, db, users):
    plain = add_resource(db, "Clinic", 10.001, 10.0, resource_type=ResourceType.HOSPITAL)
    emergency = add_resource(
        db, "ER", 10.02, 10.0, resource_type=ResourceType.HOSPITAL, capabilities=["emergency"]
    )
    db.commit()
    incident_id = _incident_with_location(client, users, "medical_emergency")
    headers = auth_headers(client, users[Role.OPERATOR])

    rows = client.get(f"/incidents/{incident_id}/recommended-resources?k=2", headers=headers).json()

    assert [r["id"] for r in rows] == [emergency.id, plain.id]
    assert rows[0]["capability_match"] is True


def test_recommendation_needs_a_visible_location(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    incident_id = client.post(
        "/incidents",
        headers=tourist,
        json={"description": "No location here", "category_code": "theft"},
    ).json()["id"]
    headers = auth_headers(client, users[Role.OPERATOR])

    response = client.get(f"/incidents/{incident_id}/recommended-resources", headers=headers)

    assert response.status_code == 409


def test_assign_is_simulated_and_audited(client, db, users):
    station = add_resource(db, "Station", 10.01, 10.0)
    db.commit()
    incident_id = _incident_with_location(client, users, "theft")
    headers = auth_headers(client, users[Role.OPERATOR])
    _acknowledge(client, headers, incident_id)

    response = client.post(
        f"/incidents/{incident_id}/assign", headers=headers, json={"resource_id": station.id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["incident"]["status"] == "ASSIGNED"
    assert body["assignment"]["simulated"] is True
    assert body["assignment"]["distance_m"] == pytest.approx(
        haversine_m(CENTER_LAT, CENTER_LON, 10.01, 10.0), rel=RELATIVE_TOLERANCE
    )
    db.refresh(station)
    assert station.availability_sim == Availability.BUSY
    assert db.scalar(
        select(AuditLog).where(
            AuditLog.action == "incident.assigned", AuditLog.target_id == str(incident_id)
        )
    )


def test_cannot_assign_new_incident_or_busy_resource(client, db, users):
    busy = add_resource(db, "Busy", 10.01, 10.0, availability=Availability.BUSY)
    free = add_resource(db, "Free", 10.02, 10.0)
    db.commit()
    incident_id = _incident_with_location(client, users, "theft")
    headers = auth_headers(client, users[Role.OPERATOR])
    url = f"/incidents/{incident_id}/assign"

    not_acknowledged = client.post(url, headers=headers, json={"resource_id": free.id})
    _acknowledge(client, headers, incident_id)
    busy_resource = client.post(url, headers=headers, json={"resource_id": busy.id})

    assert not_acknowledged.status_code == 409
    assert busy_resource.status_code == 409


def test_tourist_cannot_assign(client, db, users):
    station = add_resource(db, "Station", 10.01, 10.0)
    db.commit()
    incident_id = _incident_with_location(client, users, "theft")
    tourist = auth_headers(client, users[Role.TOURIST])

    response = client.post(
        f"/incidents/{incident_id}/assign", headers=tourist, json={"resource_id": station.id}
    )

    assert response.status_code == 403


def test_resolving_releases_the_resource(client, db, users):
    station = add_resource(db, "Station", 10.01, 10.0)
    db.commit()
    incident_id = _incident_with_location(client, users, "theft")
    headers = auth_headers(client, users[Role.OPERATOR])
    _acknowledge(client, headers, incident_id)
    client.post(
        f"/incidents/{incident_id}/assign", headers=headers, json={"resource_id": station.id}
    )

    for next_status in ["EN_ROUTE", "RESOLVED"]:
        response = client.patch(
            f"/incidents/{incident_id}/status", headers=headers, json={"status": next_status}
        )
        assert response.status_code == 200

    db.refresh(station)
    assert station.availability_sim == Availability.AVAILABLE
    assignment = db.scalar(
        select(ResponseAssignment).where(ResponseAssignment.incident_id == incident_id)
    )
    assert assignment.status == AssignmentStatus.RELEASED
