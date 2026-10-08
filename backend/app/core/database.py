"""Database connection.

`engine` holds the connection pool to PostgreSQL. `get_db` gives each API request its own
session and always closes it afterwards.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # check a pooled connection is alive before using it
    connect_args={"connect_timeout": 3},  # fail fast if PostgreSQL is not running
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
