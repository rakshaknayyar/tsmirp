"""Registration, login, tokens and the login rate limit."""

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_refresh_token
from app.models.tourist import TouristProfile
from app.models.user import Role, User
from tests.conftest import TEST_PASSWORD, auth_headers, make_user

NEW_TOURIST = {
    "email": "Asha.Traveller@tsmirp-test.in",
    "password": "a-long-enough-password",
    "full_name": "Asha Traveller",
}


def test_register_creates_tourist_with_profile(client, db):
    response = client.post("/auth/register", json=NEW_TOURIST)

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "tourist"
    assert body["email"] == "asha.traveller@tsmirp-test.in"  # stored lower-case
    assert "password" not in str(body).lower()

    user = db.scalar(select(User).where(User.id == body["id"]))
    assert user.password_hash.startswith("$argon2id$")  # hashed, never plain text
    profile = db.scalar(select(TouristProfile).where(TouristProfile.user_id == user.id))
    assert profile is not None
    assert profile.location_consent is False  # consent is off by default


def test_register_cannot_choose_a_role(client):
    response = client.post("/auth/register", json={**NEW_TOURIST, "role": "administrator"})

    assert response.status_code == 422


def test_register_rejects_duplicate_email_case_insensitive(client):
    assert client.post("/auth/register", json=NEW_TOURIST).status_code == 201
    duplicate = {**NEW_TOURIST, "email": NEW_TOURIST["email"].upper()}

    assert client.post("/auth/register", json=duplicate).status_code == 409


def test_register_rejects_short_password(client):
    response = client.post("/auth/register", json={**NEW_TOURIST, "password": "short"})

    assert response.status_code == 422


def test_login_returns_tokens_and_me_works(client, db):
    user = make_user(db, Role.TOURIST)

    headers = auth_headers(client, user)
    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == user.id


def test_wrong_password_and_unknown_email_get_the_same_answer(client, db):
    user = make_user(db, Role.TOURIST)

    wrong_password = client.post(
        "/auth/login", json={"email": user.email, "password": "nope-nope-nope"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@tsmirp-test.in", "password": TEST_PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_inactive_user_cannot_log_in(client, db):
    user = make_user(db, Role.TOURIST)
    user.is_active = False
    db.commit()

    response = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})

    assert response.status_code == 401


def test_refresh_token_gives_new_tokens(client, db):
    user = make_user(db, Role.TOURIST)
    login = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})

    response = client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_access_token_cannot_be_used_as_refresh_token(client, db):
    user = make_user(db, Role.TOURIST)
    login = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})

    response = client.post("/auth/refresh", json={"refresh_token": login.json()["access_token"]})

    assert response.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, db):
    user = make_user(db, Role.TOURIST)
    headers = {"Authorization": f"Bearer {create_refresh_token(user.id)}"}

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_missing_or_forged_token_is_rejected(client, db):
    user = make_user(db, Role.TOURIST)
    forged = jwt.encode({"sub": str(user.id), "type": "access", "exp": 9999999999}, "x" * 32)

    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_login_is_rate_limited(client, db):
    user = make_user(db, Role.TOURIST)
    attempt = {"email": user.email, "password": "wrong-password-123"}

    statuses = [
        client.post("/auth/login", json=attempt).status_code
        for _ in range(settings.login_rate_limit + 1)
    ]

    assert statuses[:-1] == [401] * settings.login_rate_limit
    assert statuses[-1] == 429
