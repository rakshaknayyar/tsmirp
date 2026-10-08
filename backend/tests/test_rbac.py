"""Role-based access control: which role may call which endpoint.

Each row of the table below is one test: (method, path, role, expected HTTP status).
"""

import pytest

from app.models.user import Role
from tests.conftest import auth_headers

NEW_STAFF = {
    "email": "new.operator@tsmirp-test.in",
    "password": "a-long-enough-password",
    "full_name": "New Operator",
    "role": "operator",
}

CASES = [
    # Tourist-only endpoints
    ("GET", "/tourist/profile", Role.TOURIST, 200),
    ("GET", "/tourist/profile", Role.OPERATOR, 403),
    ("GET", "/tourist/profile", Role.SUPERVISOR, 403),
    ("GET", "/tourist/profile", Role.ADMINISTRATOR, 403),
    # Audit log: supervisor and administrator only
    ("GET", "/audit-logs", Role.TOURIST, 403),
    ("GET", "/audit-logs", Role.OPERATOR, 403),
    ("GET", "/audit-logs", Role.SUPERVISOR, 200),
    ("GET", "/audit-logs", Role.ADMINISTRATOR, 200),
    ("GET", "/audit-logs/verify", Role.OPERATOR, 403),
    ("GET", "/audit-logs/verify", Role.SUPERVISOR, 200),
    # Creating staff accounts: administrator only
    ("POST", "/admin/users", Role.TOURIST, 403),
    ("POST", "/admin/users", Role.OPERATOR, 403),
    ("POST", "/admin/users", Role.SUPERVISOR, 403),
    ("POST", "/admin/users", Role.ADMINISTRATOR, 201),
]


@pytest.mark.parametrize(("method", "path", "role", "expected"), CASES)
def test_role_access(client, users, method, path, role, expected):
    headers = auth_headers(client, users[role])
    body = NEW_STAFF if method == "POST" else None

    response = client.request(method, path, headers=headers, json=body)

    assert response.status_code == expected


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/auth/me"),
        ("GET", "/tourist/profile"),
        ("PUT", "/tourist/consent"),
        ("GET", "/tourist/emergency-contacts"),
        ("GET", "/audit-logs"),
        ("POST", "/admin/users"),
    ],
)
def test_endpoints_require_login(client, method, path):
    assert client.request(method, path).status_code == 401


def test_admin_created_staff_has_requested_role(client, users):
    headers = auth_headers(client, users[Role.ADMINISTRATOR])

    response = client.post("/admin/users", headers=headers, json=NEW_STAFF)

    assert response.status_code == 201
    assert response.json()["role"] == "operator"
