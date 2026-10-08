"""Phase 9: the digital tourist ID (signed, time-limited QR credential)."""

from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.user import Role
from tests.conftest import auth_headers


def _credential(client, user) -> dict:
    response = client.get("/tourist/credential", headers=auth_headers(client, user))
    assert response.status_code == 200
    return response.json()


def _verify(client, staff, token: str) -> dict:
    headers = auth_headers(client, staff)
    response = client.post("/credential/verify", headers=headers, json={"token": token})
    assert response.status_code == 200
    return response.json()


def test_tourist_gets_a_credential_with_qr_code(client, db, users):
    body = _credential(client, users[Role.TOURIST])

    assert body["qr_svg"].startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    lifetime = datetime.fromisoformat(body["expires_at"]) - datetime.fromisoformat(
        body["issued_at"]
    )
    assert lifetime == timedelta(days=settings.credential_days)
    claims = jwt.decode(body["token"], options={"verify_signature": False})
    assert set(claims) == {"sub", "type", "iat", "exp", "name", "nationality"}  # no location
    assert db.scalar(select(AuditLog).where(AuditLog.action == "credential.issued"))


def test_staff_can_verify_a_genuine_credential(client, db, users):
    token = _credential(client, users[Role.TOURIST])["token"]

    result = _verify(client, users[Role.OPERATOR], token)

    assert result["valid"] is True
    assert result["user_id"] == users[Role.TOURIST].id
    assert result["full_name"] == users[Role.TOURIST].full_name
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "credential.verified"))
    assert audit.details == {"valid": True}  # the token itself is not stored


def test_altered_credential_is_rejected(client, users):
    token = _credential(client, users[Role.TOURIST])["token"]
    header, payload, signature = token.split(".")
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["name"] = "Someone Else"
    forged_payload = jwt.encode(claims, "wrong-secret-" * 4, algorithm="HS256").split(".")[1]

    result = _verify(client, users[Role.OPERATOR], f"{header}.{forged_payload}.{signature}")

    assert result["valid"] is False
    assert result["full_name"] is None


def test_expired_credential_is_rejected(client, users):
    past = datetime.now(UTC) - timedelta(days=1)
    expired = jwt.encode(
        {"sub": str(users[Role.TOURIST].id), "type": "tourist_credential", "exp": past},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    assert _verify(client, users[Role.OPERATOR], expired)["valid"] is False


def test_login_token_is_not_a_credential_and_credential_cannot_log_in(client, users):
    tourist = users[Role.TOURIST]
    access = create_access_token(tourist.id)
    credential = _credential(client, tourist)["token"]

    assert _verify(client, users[Role.OPERATOR], access)["valid"] is False
    as_login = client.get("/auth/me", headers={"Authorization": f"Bearer {credential}"})
    assert as_login.status_code == 401


def test_credential_of_deactivated_account_is_rejected(client, db, users):
    tourist = users[Role.TOURIST]
    token = _credential(client, tourist)["token"]
    tourist.is_active = False
    db.commit()

    assert _verify(client, users[Role.OPERATOR], token)["valid"] is False


def test_credential_roles(client, users):
    operator = auth_headers(client, users[Role.OPERATOR])
    tourist = auth_headers(client, users[Role.TOURIST])

    assert client.get("/tourist/credential", headers=operator).status_code == 403
    verify = client.post("/credential/verify", headers=tourist, json={"token": "x" * 20})
    assert verify.status_code == 403
