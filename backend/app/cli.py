"""Command-line tools.

Create the first administrator (staff cannot sign up through the public API):

    python -m app.cli create-admin --email admin@example.org --name "Admin Name"

The password is typed in hidden and never printed or stored in plain text.
"""

import argparse
import getpass
import sys

from app.core.database import SessionLocal
from app.models.user import Role
from app.services.audit import record_event
from app.services.users import EmailAlreadyRegistered, create_user

MIN_PASSWORD_LENGTH = 10


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin_cmd = commands.add_parser("create-admin", help="create an administrator account")
    admin_cmd.add_argument("--email", required=True)
    admin_cmd.add_argument("--name", required=True)

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name)


if __name__ == "__main__":
    main()
