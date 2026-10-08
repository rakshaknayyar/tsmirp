"""Shared parent class for every database table.

Tables are added from Phase 1 onwards; each one inherits from `Base` so Alembic can find it.
"""

import enum

from sqlalchemy import Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

# Predictable constraint names, so Alembic migrations can rename/drop them reliably.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def text_enum(enum_class: type[enum.Enum], length: int) -> Enum:
    """A Python enum stored as plain text (its values, e.g. "NEW").
    The allowed values are enforced by CHECK constraints written in the migrations."""
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
    )
