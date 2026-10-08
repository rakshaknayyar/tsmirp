"""Import police stations, hospitals and fire stations from OpenStreetMap.

Data source: OpenStreetMap contributors, via the Overpass API.
Licence: Open Database License (ODbL) - attribution is in the README and the map.

Steps:
1. fetch_overpass()   download every amenity=police / hospital / fire_station in the area
2. parse_overpass()   turn the raw JSON into simple ResourceRecord objects
3. upsert_resources() insert new ones, update ones we already have (matched by OSM id)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resource import Availability, ResourceType, ResponseResource

# Public Overpass servers are often busy, so we try these in order.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


@dataclass(frozen=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float


# The single demo area of the prototype. Roughly central Jaipur, Rajasthan.
DEMO_AREAS = {"jaipur": BoundingBox(south=26.80, west=75.70, north=27.00, east=75.90)}

AMENITY_TO_TYPE = {
    "police": ResourceType.POLICE_STATION,
    "hospital": ResourceType.HOSPITAL,
    "fire_station": ResourceType.FIRE_STATION,
}


@dataclass
class ResourceRecord:
    source_ref: str  # "node/123" or "way/456"
    name: str
    resource_type: ResourceType
    lat: float
    lon: float
    capabilities: list[str] = field(default_factory=list)


def build_query(box: BoundingBox) -> str:
    bbox = f"{box.south},{box.west},{box.north},{box.east}"
    amenities = "|".join(AMENITY_TO_TYPE)
    # "out center" gives buildings (ways) a single centre point.
    return (
        "[out:json][timeout:90];"
        f'(node["amenity"~"^({amenities})$"]({bbox});'
        f'way["amenity"~"^({amenities})$"]({bbox}););'
        "out center tags;"
    )


class OverpassUnavailable(Exception):
    pass


def fetch_overpass(box: BoundingBox) -> dict:
    errors = []
    for url in OVERPASS_URLS:
        try:
            response = httpx.post(
                url,
                data={"data": build_query(box)},
                headers={"User-Agent": "TSMIRP-student-prototype (SIH25002)"},
                timeout=120,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:  # ValueError: reply was not JSON
            errors.append(f"{url}: {type(exc).__name__} {exc}")
    raise OverpassUnavailable("All Overpass servers failed:\n" + "\n".join(errors))


def parse_overpass(data: dict) -> list[ResourceRecord]:
    records = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        resource_type = AMENITY_TO_TYPE.get(tags.get("amenity"))
        # Nodes have lat/lon; ways have a "center" (because of "out center").
        point = element if "lat" in element else element.get("center")
        if resource_type is None or point is None:
            continue

        name = tags.get("name:en") or tags.get("name")
        if not name:
            name = f"Unnamed {resource_type.value.replace('_', ' ')}"
        capabilities = []
        if resource_type == ResourceType.HOSPITAL and tags.get("emergency") == "yes":
            capabilities.append("emergency")  # has an emergency department

        records.append(
            ResourceRecord(
                source_ref=f"{element['type']}/{element['id']}",
                name=name[:200],
                resource_type=resource_type,
                lat=point["lat"],
                lon=point["lon"],
                capabilities=capabilities,
            )
        )
    return records


def upsert_resources(db: Session, records: list[ResourceRecord]) -> tuple[int, int]:
    """Insert or update resources. Simulated availability is kept for existing rows.
    Returns (created, updated). The caller commits."""
    created = updated = 0
    for record in records:
        geog = WKTElement(f"POINT({record.lon} {record.lat})", srid=4326)
        existing = db.scalar(
            select(ResponseResource).where(ResponseResource.source_ref == record.source_ref)
        )
        if existing is None:
            db.add(
                ResponseResource(
                    name=record.name,
                    resource_type=record.resource_type,
                    geog=geog,
                    source="osm",
                    source_ref=record.source_ref,
                    capabilities=record.capabilities,
                    availability_sim=Availability.AVAILABLE,
                )
            )
            created += 1
        else:
            existing.name = record.name
            existing.resource_type = record.resource_type
            existing.geog = geog
            existing.capabilities = record.capabilities
            updated += 1
    db.flush()
    return created, updated


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
