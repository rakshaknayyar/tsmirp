"""Tests for GET /health.

The database test is SKIPPED (not failed) when PostgreSQL is not reachable on your machine,
and the reason is printed. In CI we set REQUIRE_DB=1 so a missing database FAILS instead.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_responds():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "ok"
    assert {"status", "database", "redis"} <= body.keys()


def test_health_does_not_leak_password():
    body_text = client.get("/health").text.lower()

    assert "password" not in body_text


def test_database_reachable_with_postgis():
    database = client.get("/health").json()["database"]

    if database["status"] != "ok":
        message = f"PostgreSQL not reachable ({database.get('error')}); check .env"
        if os.getenv("REQUIRE_DB") == "1":
            pytest.fail(message)
        pytest.skip(message)

    assert database["postgis_version"], "PostGIS not enabled - run `alembic upgrade head`"
