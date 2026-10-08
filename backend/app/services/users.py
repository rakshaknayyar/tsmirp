"""Creating user accounts (shared by registration, the admin API and the CLI)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tourist import TouristProfile
from app.models.user import Role, User


class EmailAlreadyRegistered(Exception):
    pass


def create_user(db: Session, *, email: str, password: str, full_name: str, role: Role) -> User:
    """Add a user (and a tourist profile for tourists). The caller audits and commits."""
    email = email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailAlreadyRegistered(email)

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()  # sends the INSERT so user.id is known

    if role == Role.TOURIST:
        db.add(TouristProfile(user_id=user.id))
        db.flush()
    return user
