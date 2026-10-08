"""Shared test fixtures.

- The database is migrated to the latest version once per test run.
- Each test runs inside one database transaction that is ROLLED BACK afterwards, so tests
  never leave data behind and cannot affect each other.
- If PostgreSQL is not reachable, database tests are skipped (or fail in CI, REQUIRE_DB=1).
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.rate_limit import login_limiter, sos_limiter
from app.main import app
from app.models.user import Role, User
from app.services.users import create_user

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def migrated_engine() -> Engine:
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        message = f"PostgreSQL not reachable ({type(exc).__name__}); check .env"
        if os.getenv("REQUIRE_DB") == "1":
            pytest.fail(message)
        pytest.skip(message)

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    return engine


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    connection = migrated_engine.connect()
    transaction = connection.begin()
    # "create_savepoint": a db.commit() inside the app only commits a savepoint, so the
    # outer transaction can still roll everything back at the end of the test.
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@contextmanager
def app_client(db: Session) -> Iterator[TestClient]:
    """A test client whose requests all use the test's (rolled-back) database session.
    Using it as a context manager also runs the app's startup/shutdown (the event bus)."""
    app.dependency_overrides[get_db] = lambda: db
    login_limiter.reset()
    sos_limiter.reset()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # In-process events, so tests do not depend on Redis (test_dashboard.py checks Redis).
    monkeypatch.setattr(settings, "event_backend", "memory")
    with app_client(db) as test_client:
        yield test_client


def make_user(db: Session, role: Role, name: str | None = None) -> User:
    label = name or role.value
    user = create_user(
        db,
        email=f"{label}@tsmirp-test.in",
        password=TEST_PASSWORD,
        full_name=f"Test {label}",
        role=role,
    )
    db.commit()
    return user


def auth_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def users(db: Session) -> dict[Role, User]:
    """One user of every role."""
    return {role: make_user(db, role) for role in Role}
