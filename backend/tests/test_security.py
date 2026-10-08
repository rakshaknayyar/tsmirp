"""Phase 9: checks for the OWASP API Security Top 10 (2023).

Many of the risks are already tested in earlier files (named in docs/security.md). This file
adds the checks that look at the API as a whole, so a new endpoint cannot silently skip them.
"""

import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.main import app
from app.models.user import Role
from tests.conftest import auth_headers

# Endpoints that deliberately work without logging in.
PUBLIC = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
}


def _api_routes() -> list[tuple[str, str]]:
    """Every documented endpoint, from the OpenAPI description (the API's own inventory)."""
    paths = app.openapi()["paths"]
    return sorted((method.upper(), path) for path, ops in paths.items() for method in ops)


# ---------- API2: broken authentication / API9: improper inventory management ----------


@pytest.mark.parametrize(("method", "path"), [r for r in _api_routes() if r not in PUBLIC])
def test_every_endpoint_requires_login(client, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)  # e.g. /incidents/{incident_id} -> /incidents/1

    assert client.request(method, url).status_code == 401


def test_public_endpoints_exist_and_the_inventory_is_complete():
    routes = set(_api_routes())

    assert PUBLIC <= routes
    assert len(routes) >= 30  # guards against the list above silently becoming empty


def _token(user_id: int, **changes) -> str:
    claims = {"sub": str(user_id), "type": "access", "exp": datetime.now(UTC) + timedelta(hours=1)}
    claims.update(changes)
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_expired_and_unsigned_tokens_are_rejected(client, users):
    user_id = users[Role.ADMINISTRATOR].id
    expired = _token(user_id, exp=datetime.now(UTC) - timedelta(seconds=1))
    unsigned = jwt.encode({"sub": str(user_id), "type": "access"}, key=None, algorithm="none")
    other_key = jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "not-the-server-secret-" * 2,
        algorithm="HS256",
    )

    for token in (expired, unsigned, other_key):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {_token(user_id)}"}).is_success


# ---------- API3: broken object property level authorisation ----------


def test_password_hash_is_never_returned(client, users):
    admin = auth_headers(client, users[Role.ADMINISTRATOR])
    new_staff = {
        "email": "another.operator@tsmirp-test.in",
        "password": "a-long-enough-password",
        "full_name": "Another Operator",
        "role": "operator",
    }
    registered = client.post(
        "/auth/register",
        json={"email": "new.t@tsmirp-test.in", "password": "a-long-password", "full_name": "T"},
    )

    for body in (
        registered.json(),
        client.get("/auth/me", headers=admin).json(),
        client.post("/admin/users", headers=admin, json=new_staff).json(),
    ):
        assert not any("password" in key for key in body)


def test_unknown_fields_are_rejected_not_ignored(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])

    sneaky = {"description": "A normal report", "status": "CLOSED", "reporter_user_id": 1}
    assert client.post("/incidents", headers=tourist, json=sneaky).status_code == 422
    sos = client.post("/sos", headers=tourist, json={"severity": "LOW"})
    assert sos.status_code == 422


# ---------- API4: unrestricted resource consumption ----------


def test_sizes_and_page_lengths_are_limited(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])

    assert client.get("/incidents?limit=201", headers=tourist).status_code == 422
    long_report = {"description": "x" * 2001}
    assert client.post("/incidents", headers=tourist, json=long_report).status_code == 422
    huge_box = "/risk-zone?bbox=60,0,100,40"  # far bigger than one city
    assert client.get(huge_box, headers=tourist).status_code == 422


# ---------- API5: broken function level authorisation ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/analytics/summary"),
        ("POST", "/risk/predict"),
        ("POST", "/credential/verify"),
        ("GET", "/audit-logs"),
        ("POST", "/admin/users"),
        ("PATCH", "/incidents/1/status"),
        ("GET", "/incidents/1/recommended-resources"),
        ("POST", "/incidents/1/assign"),
        ("GET", "/tourist/location/1"),
    ],
)
def test_tourists_cannot_call_staff_functions(client, users, method, path):
    tourist = auth_headers(client, users[Role.TOURIST])

    assert client.request(method, path, headers=tourist, json={}).status_code == 403


# ---------- API7: server-side request forgery ----------


def test_no_endpoint_accepts_a_url_from_the_user():
    """The server only fetches fixed addresses (Overpass, Open-Meteo, set in code), so no
    request field may contain a URL that the server would then fetch."""
    schemas = app.openapi()["components"]["schemas"]

    for name, schema in schemas.items():
        for field, spec in schema.get("properties", {}).items():
            assert "url" not in field.lower() and spec.get("format") != "uri", (name, field)


# ---------- API8: security misconfiguration ----------


def test_no_cross_origin_access_and_plain_errors(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers  # no CORS: same origin only

    missing = client.get("/no-such-endpoint")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}  # no stack trace or version details
