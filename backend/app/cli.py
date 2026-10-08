"""Command-line tools.

Create the first administrator (staff cannot sign up through the public API):

    python -m app.cli create-admin --email admin@example.org --name "Admin Name"

The password is typed in hidden and never printed or stored in plain text.

Import police stations, hospitals and fire stations from OpenStreetMap for the demo area:

    python -m app.cli import-osm --area jaipur
    python -m app.cli import-osm --area jaipur --from-file ../ml/data/raw/osm_jaipur.json

A download is saved to ml/data/raw/osm_<area>.json so the import can be repeated offline.

Load the SYNTHETIC demo risk zones (hand-made, not crime data):

    python -m app.cli seed-zones
"""

import argparse
import getpass
import sys
from pathlib import Path

from app.core.config import REPO_ROOT
from app.core.database import SessionLocal
from app.models.user import Role
from app.services import osm_import
from app.services.audit import record_event
from app.services.users import EmailAlreadyRegistered, create_user
from app.services.zones import seed_zones

MIN_PASSWORD_LENGTH = 10
DEFAULT_ZONES_FILE = REPO_ROOT / "ml" / "data" / "synthetic_risk_zones_jaipur.json"


def create_admin(email: str, full_name: str) -> None:
    password = getpass.getpass(f"New administrator password (min {MIN_PASSWORD_LENGTH} chars): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit("Password too short.")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")

    with SessionLocal() as db:
        try:
            user = create_user(
                db, email=email, password=password, full_name=full_name, role=Role.ADMINISTRATOR
            )
        except EmailAlreadyRegistered:
            sys.exit("That e-mail is already registered.")
        record_event(
            db,
            "user.created_by_cli",
            target_type="user",
            target_id=user.id,
            details={"role": Role.ADMINISTRATOR.value},
        )
        db.commit()
    print(f"Administrator created (user id {user.id}).")


def import_osm(area: str, from_file: Path | None) -> None:
    box = osm_import.DEMO_AREAS[area]
    if from_file is not None:
        data = osm_import.load_json(from_file)
        print(f"Loaded {from_file}")
    else:
        print(f"Downloading {area} from the OpenStreetMap Overpass API (can take a minute)...")
        data = osm_import.fetch_overpass(box)
        raw_path = REPO_ROOT / "ml" / "data" / "raw" / f"osm_{area}.json"
        osm_import.save_json(data, raw_path)
        print(f"Saved raw download to {raw_path}")

    records = osm_import.parse_overpass(data)
    with SessionLocal() as db:
        created, updated = osm_import.upsert_resources(db, records)
        record_event(
            db,
            "resources.imported",
            details={"area": area, "source": "osm", "created": created, "updated": updated},
        )
        db.commit()

    counts: dict[str, int] = {}
    for record in records:
        counts[record.resource_type.value] = counts.get(record.resource_type.value, 0) + 1
    print(f"Parsed {len(records)} resources: {counts}")
    print(f"Created {created}, updated {updated}. Data (c) OpenStreetMap contributors, ODbL.")


def seed_zones_command(path: Path) -> None:
    with SessionLocal() as db:
        created, updated = seed_zones(db, path)
        record_event(
            db,
            "risk_zones.seeded",
            details={"file": path.name, "created": created, "updated": updated, "synthetic": True},
        )
        db.commit()
    print(f"Risk zones from {path.name}: created {created}, updated {updated} (SYNTHETIC data).")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    admin_cmd = commands.add_parser("create-admin", help="create an administrator account")
    admin_cmd.add_argument("--email", required=True)
    admin_cmd.add_argument("--name", required=True)

    osm_cmd = commands.add_parser("import-osm", help="import resources from OpenStreetMap")
    osm_cmd.add_argument("--area", choices=sorted(osm_import.DEMO_AREAS), default="jaipur")
    osm_cmd.add_argument("--from-file", type=Path, help="use a saved Overpass JSON file")

    zones_cmd = commands.add_parser("seed-zones", help="load the synthetic demo risk zones")
    zones_cmd.add_argument("--file", type=Path, default=DEFAULT_ZONES_FILE)

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name)
    elif args.command == "import-osm":
        import_osm(args.area, args.from_file)
    elif args.command == "seed-zones":
        seed_zones_command(args.file)


if __name__ == "__main__":
    main()
