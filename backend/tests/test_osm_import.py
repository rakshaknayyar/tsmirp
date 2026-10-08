"""Parsing and upserting OpenStreetMap data, using a small hand-written sample (no network)."""

from sqlalchemy import func, select

from app.models.resource import Availability, ResourceType, ResponseResource
from app.services.osm_import import DEMO_AREAS, build_query, parse_overpass, upsert_resources

SAMPLE = {
    "elements": [
        {
            "type": "node",
            "id": 9000000001,
            "lat": 26.9200,
            "lon": 75.8000,
            "tags": {"amenity": "police", "name": "Test Police Station"},
        },
        {
            "type": "way",
            "id": 9000000002,
            "center": {"lat": 26.9000, "lon": 75.8100},
            "tags": {"amenity": "hospital", "name": "Test Hospital", "emergency": "yes"},
        },
        {
            "type": "node",
            "id": 9000000003,
            "lat": 26.8800,
            "lon": 75.7900,
            "tags": {"amenity": "fire_station"},  # no name
        },
        {
            "type": "node",
            "id": 9000000004,
            "lat": 26.8700,
            "lon": 75.7800,
            "tags": {"amenity": "restaurant", "name": "Not a resource"},
        },
        {"type": "way", "id": 9000000005, "tags": {"amenity": "police"}},  # no coordinates
    ]
}


def test_query_mentions_all_three_amenities_and_the_box():
    query = build_query(DEMO_AREAS["jaipur"])

    assert "police|hospital|fire_station" in query
    assert "26.8,75.7,27.0,75.9" in query


def test_parse_keeps_only_resources_with_coordinates():
    records = parse_overpass(SAMPLE)

    assert [r.source_ref for r in records] == [
        "node/9000000001",
        "way/9000000002",
        "node/9000000003",
    ]


def test_parse_reads_names_types_and_capabilities():
    police, hospital, fire = parse_overpass(SAMPLE)

    assert police.resource_type == ResourceType.POLICE_STATION
    assert hospital.lat == 26.9000  # taken from the way's centre point
    assert hospital.capabilities == ["emergency"]
    assert fire.name == "Unnamed fire station"


def test_upsert_twice_does_not_duplicate(db):
    records = parse_overpass(SAMPLE)

    first = upsert_resources(db, records)
    records[0].name = "Renamed Police Station"
    second = upsert_resources(db, records)

    assert first == (3, 0)
    assert second == (0, 3)
    count = db.scalar(select(func.count()).where(ResponseResource.source_ref.like("%/900000000%")))
    assert count == 3
    renamed = db.scalar(
        select(ResponseResource).where(ResponseResource.source_ref == "node/9000000001")
    )
    assert renamed.name == "Renamed Police Station"
    assert renamed.availability_sim == Availability.AVAILABLE
