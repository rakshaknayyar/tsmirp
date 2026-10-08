"""Tourist profile, location consent, and emergency contacts (including ownership checks)."""

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.user import Role
from tests.conftest import auth_headers, make_user

CONTACT = {"name": "Ravi Kumar", "phone": "+91 98765 43210", "relation": "brother"}


def test_consent_is_off_until_granted(client, db):
    headers = auth_headers(client, make_user(db, Role.TOURIST))

    profile = client.get("/tourist/profile", headers=headers).json()

    assert profile["location_consent"] is False
    assert profile["consent_time"] is None


def test_grant_and_revoke_consent_are_recorded_and_audited(client, db):
    tourist = make_user(db, Role.TOURIST)
    headers = auth_headers(client, tourist)

    granted = client.put("/tourist/consent", headers=headers, json={"location_consent": True})
    revoked = client.put("/tourist/consent", headers=headers, json={"location_consent": False})

    assert granted.json()["location_consent"] is True
    assert granted.json()["consent_time"] is not None
    assert revoked.json()["location_consent"] is False
    actions = db.scalars(
        select(AuditLog.action)
        .where(AuditLog.actor_user_id == tourist.id, AuditLog.action.like("consent.%"))
        .order_by(AuditLog.id)
    ).all()
    assert actions == ["consent.location_granted", "consent.location_revoked"]


def test_profile_update_cannot_change_consent(client, db):
    headers = auth_headers(client, make_user(db, Role.TOURIST))

    response = client.put("/tourist/profile", headers=headers, json={"location_consent": True})

    assert response.status_code == 422


def test_profile_update(client, db):
    headers = auth_headers(client, make_user(db, Role.TOURIST))
    update = {"nationality": "Indian", "phone": "+91 99999 00000", "preferred_language": "hi"}

    response = client.put("/tourist/profile", headers=headers, json=update)

    assert response.status_code == 200
    assert response.json()["preferred_language"] == "hi"


def test_add_list_and_delete_own_contact(client, db):
    headers = auth_headers(client, make_user(db, Role.TOURIST))

    created = client.post("/tourist/emergency-contacts", headers=headers, json=CONTACT)
    listed = client.get("/tourist/emergency-contacts", headers=headers)
    deleted = client.delete(f"/tourist/emergency-contacts/{created.json()['id']}", headers=headers)

    assert created.status_code == 201
    assert [c["name"] for c in listed.json()] == ["Ravi Kumar"]
    assert deleted.status_code == 204
    assert client.get("/tourist/emergency-contacts", headers=headers).json() == []


def test_tourist_cannot_see_or_delete_another_tourists_contact(client, db):
    owner_headers = auth_headers(client, make_user(db, Role.TOURIST, name="owner"))
    other_headers = auth_headers(client, make_user(db, Role.TOURIST, name="other"))
    contact_id = client.post(
        "/tourist/emergency-contacts", headers=owner_headers, json=CONTACT
    ).json()["id"]

    other_list = client.get("/tourist/emergency-contacts", headers=other_headers)
    other_delete = client.delete(f"/tourist/emergency-contacts/{contact_id}", headers=other_headers)

    assert other_list.json() == []
    assert other_delete.status_code == 404  # same answer as "does not exist": nothing leaks
    owner_list = client.get("/tourist/emergency-contacts", headers=owner_headers)
    assert [c["id"] for c in owner_list.json()] == [contact_id]


def test_invalid_phone_is_rejected(client, db):
    headers = auth_headers(client, make_user(db, Role.TOURIST))

    response = client.post(
        "/tourist/emergency-contacts", headers=headers, json={**CONTACT, "phone": "call me"}
    )

    assert response.status_code == 422
