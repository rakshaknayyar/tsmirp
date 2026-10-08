"""Users table and the four roles."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Role(enum.StrEnum):
    TOURIST = "tourist"
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMINISTRATOR = "administrator"


# Everyone who works on the authority side (sees all incidents, uses the dashboard).
STAFF_ROLES = frozenset({Role.OPERATOR, Role.SUPERVISOR, Role.ADMINISTRATOR})


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # always stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    # Stored as text. The database CHECK constraint "ck_users_role" (migration 0002) only
    # allows the four role values; Python also rejects unknown values when loading.
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            native_enum=False,
            length=20,
            values_callable=lambda roles: [r.value for r in roles],
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
