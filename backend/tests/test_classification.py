"""Text model (generator, training, reproducibility) and the classification features of the API.

The model is trained once per test run (fixtures `trained_text_model` / `text_model` in
conftest.py), so these tests never depend on a model trained earlier on this machine.
"""

import sys

from sqlalchemy import select

from app.core.config import REPO_ROOT
from app.core.rate_limit import classify_limiter
from app.models.audit import AuditLog
from app.models.user import Role
from tests.conftest import auth_headers

sys.path.insert(0, str(REPO_ROOT))  # so the ml/ folder can be imported
from ml.text_data import CATEGORIES, LANGUAGES, generate_texts  # noqa: E402
from ml.train_text_classifier import split_by_template, train  # noqa: E402

BRIEF_EXAMPLE = "My phone was stolen near the market"


# ---------- synthetic data ----------


def test_generator_is_deterministic_and_labelled():
    first = generate_texts(seed=7)
    second = generate_texts(seed=7)

    assert first == second
    assert all(row.synthetic for row in first)
    assert {row.category for row in first} == set(CATEGORIES)
    assert {row.language for row in first} == set(LANGUAGES)


def test_generator_categories_match_the_database(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    codes = {c["code"] for c in client.get("/incident-categories", headers=headers).json()}

    assert codes == set(CATEGORIES)


def test_train_and_test_never_share_a_template():
    rows = [r for r in generate_texts(seed=42) if r.language == "en"]

    train_rows, test_rows = split_by_template(rows, 0.25, seed=42)

    assert {r.template_id for r in train_rows}.isdisjoint({r.template_id for r in test_rows})
    assert {r.category for r in test_rows} == set(CATEGORIES)


# ---------- training ----------


def test_training_writes_versioned_artefacts(trained_text_model):
    artefacts, result = trained_text_model
    version = (artefacts / "LATEST").read_text()

    assert version == result["version"]
    for name in ["model.joblib", "metadata.json", "metrics.json"]:
        assert (artefacts / version / name).is_file()
    assert result["metrics"]["macro_f1"] > result["metrics"]["baseline_most_frequent"]["macro_f1"]


def test_training_is_reproducible(trained_text_model, tmp_path):
    _, first = trained_text_model

    second = train(tmp_path / "artefacts", tmp_path / "texts.csv", report_path=None)

    assert second["version"] == first["version"]
    assert second["metrics"]["macro_f1"] == first["metrics"]["macro_f1"]


# ---------- POST /incident/classify ----------


def test_brief_example_is_theft_high_police(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incident/classify", headers=headers, json={"text": BRIEF_EXAMPLE}).json()

    assert body["category"]["code"] == "theft"
    assert body["severity"] == "HIGH"
    assert body["category"]["department"] == "Police"
    assert 0 <= body["confidence"] <= 1
    assert body["model_version"].startswith("textclf-")
    assert "synthetic" in body["note"]


def test_meaningless_text_is_flagged_for_review(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incident/classify", headers=headers, json={"text": "zzzz qqqq"}).json()

    assert body["needs_review"] is True


def test_english_text_is_not_translated(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incident/classify", headers=headers, json={"text": BRIEF_EXAMPLE}).json()

    assert (body["language"], body["language_detected"]) == ("en", True)
    assert body["english_text"] == BRIEF_EXAMPLE
    assert body["translation_method"] is None


def test_classify_without_model_is_503(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    response = client.post("/incident/classify", headers=headers, json={"text": BRIEF_EXAMPLE})

    assert response.status_code == 503


def test_classify_needs_login_and_is_rate_limited(client, users, text_model, monkeypatch):
    monkeypatch.setattr(classify_limiter, "max_requests", 2)
    headers = auth_headers(client, users[Role.TOURIST])
    body = {"text": BRIEF_EXAMPLE}

    assert client.post("/incident/classify", json=body).status_code == 401
    statuses = [
        client.post("/incident/classify", headers=headers, json=body).status_code for _ in range(3)
    ]
    assert statuses == [200, 200, 429]


def test_classify_rejects_half_a_location(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    response = client.post(
        "/incident/classify", headers=headers, json={"text": BRIEF_EXAMPLE, "lat": 26.9}
    )

    assert response.status_code == 422


# ---------- automatic classification of new reports ----------


def test_report_without_category_is_classified(client, db, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incidents", headers=headers, json={"description": BRIEF_EXAMPLE}).json()

    assert body["category"]["code"] == "theft"
    assert body["severity"] == "HIGH"
    assert body["confidence"] is not None
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "incident.reported"))
    assert audit.details["classified_automatically"] is True
    assert audit.details["model_version"].startswith("textclf-")


def test_report_without_category_and_without_model_needs_review(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incidents", headers=headers, json={"description": BRIEF_EXAMPLE}).json()

    assert body["category"] is None
    assert body["needs_review"] is True
    assert body["severity"] == "MEDIUM"  # default when the category is unknown


# ---------- operator override ----------


def test_operator_can_override_and_it_is_audited(client, db, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])
    sos_id = client.post("/sos", headers=tourist, json={}).json()["incident"]["id"]

    response = client.patch(
        f"/incidents/{sos_id}",
        headers=operator,
        json={"severity": "MEDIUM", "category_code": "other", "note": "accidental press"},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["severity"], body["category"]["code"]) == ("MEDIUM", "other")
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "incident.override"))
    assert audit.details["severity"] == {"from": "CRITICAL", "to": "MEDIUM"}
    assert audit.details["note"] == "accidental press"


def test_override_confirms_the_category_and_clears_review(client, users, text_model):
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])
    incident = client.post("/incidents", headers=tourist, json={"description": "zzzz qqqq"}).json()
    assert incident["needs_review"] is True

    body = client.patch(
        f"/incidents/{incident['id']}", headers=operator, json={"category_code": "other"}
    ).json()

    assert body["needs_review"] is False
    assert body["confidence"] is None  # now decided by a person


def test_override_rules(client, users):
    tourist = auth_headers(client, users[Role.TOURIST])
    operator = auth_headers(client, users[Role.OPERATOR])
    incident_id = client.post(
        "/incidents", headers=tourist, json={"description": BRIEF_EXAMPLE, "category_code": "theft"}
    ).json()["id"]
    url = f"/incidents/{incident_id}"

    assert client.patch(url, headers=tourist, json={"severity": "LOW"}).status_code == 403
    assert client.patch(url, headers=operator, json={}).status_code == 422
    assert client.patch(url, headers=operator, json={"category_code": "aliens"}).status_code == 422
