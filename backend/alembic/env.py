"""Alembic migration environment.

Connects Alembic to the same database settings and table definitions (Base.metadata) that
the API uses, so migrations always target the right database.
"""

from logging.config import fileConfig

from alembic import context

from app.core.database import engine
from app.models import Base  # importing app.models loads every table definition

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tables created by the PostGIS extension itself; Alembic must not try to manage them.
POSTGIS_TABLES = {"spatial_ref_sys"}


def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "table" and name in POSTGIS_TABLES)


def run_migrations_offline() -> None:
    """Write migration SQL to the screen instead of running it (alembic upgrade --sql)."""
    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and run the migrations."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
