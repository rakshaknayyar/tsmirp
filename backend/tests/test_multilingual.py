"""Phase 8: language detection, the word-list translator, and "translate, then classify" in
POST /incident/classify and POST /incidents."""

import unicodedata

import pytest
from sqlalchemy import select

from app.ml.language import detect_language
from app.ml.translator import Translation, WordListTranslator, get_translator
from app.models.audit import AuditLog
from app.models.user import Role
from app.services.language import prepare_text
from tests.conftest import auth_headers

ROMANISED_THEFT = "Mera phone chori ho gaya hai"
HINDI_FIRE = "होटल के कमरे में आग लग गई है"


# ---------- language detection ----------


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("My phone was stolen near the market", "en"),
        ("I left my bag at the hotel", "en"),
        ("Help! There is a fire", "en"),
        (ROMANISED_THEFT, "hi-Latn"),
        ("Ek aadmi mera peecha kar raha hai", "hi-Latn"),
        (HINDI_FIRE, "hi"),
        ("मेरा फ़ोन चोरी हो गया", "hi"),
    ],
)
def test_detect_language(text, language):
    assert detect_language(text) == language


# ---------- translator ----------


def test_romanised_hindi_is_translated_keeping_english_words():
    result = get_translator().translate(ROMANISED_THEFT, "hi-Latn")

    assert result.text == "my phone was stolen"  # "phone" kept, "chori ho gaya" -> phrase
    assert result.unknown_words == ["phone"]  # not in the list, kept because it is English
    assert result.method == "wordlist-v1"


def test_devanagari_is_translated_and_unknown_words_are_reported():
    result = get_translator().translate("होटल में आग लग गई और शोर है", "hi")

    assert "fire" in result.text and "hotel" in result.text
    assert "शोर" in result.unknown_words  # "noise": not in the word list, so it is lost


def test_letters_with_a_dot_match_however_they_are_typed():
    precomposed = "\u095b"  # ज़ as one character
    decomposed = unicodedata.normalize("NFD", precomposed)  # ज + dot below
    assert precomposed != decomposed

    for zyada in (f"{precomposed}्यादा", f"{decomposed}्यादा"):
        assert get_translator().translate(f"{zyada} पैसे", "hi").text == "more money"


def test_unknown_language_is_refused():
    with pytest.raises(ValueError):
        WordListTranslator().translate("bonjour", "fr")


def test_prepare_text_uses_the_translator_interface(monkeypatch):
    class FakeTranslator:  # any class with translate() can replace the word list
        def translate(self, text, source_language):
            return Translation("fake english", source_language, "fake", 1)

    monkeypatch.setattr("app.services.language.get_translator", lambda: FakeTranslator())

    prepared = prepare_text(ROMANISED_THEFT)

    assert (prepared.language, prepared.english) == ("hi-Latn", "fake english")
    assert prepared.text_for_rules == f"{ROMANISED_THEFT} fake english"


def test_given_language_overrides_detection():
    prepared = prepare_text("I left my bag at the hotel", "en")

    assert prepared.language_detected is False
    assert prepared.translation is None


# ---------- classify endpoint ----------


def test_romanised_hindi_report_is_translated_then_classified(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incident/classify", headers=headers, json={"text": ROMANISED_THEFT}).json()

    assert (body["language"], body["language_detected"]) == ("hi-Latn", True)
    assert body["english_text"] == "my phone was stolen"
    assert body["category"]["code"] == "theft"
    assert body["severity"] == "HIGH"  # theft of a phone: English rule on the translation
    assert body["translation_method"] == "wordlist-v1"
    assert "translated word by word" in body["note"]


def test_hindi_fire_report_is_critical(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incident/classify", headers=headers, json={"text": HINDI_FIRE}).json()

    assert body["language"] == "hi"
    assert body["category"]["code"] == "fire"
    assert body["severity"] == "CRITICAL"


def test_untranslatable_text_always_goes_to_review(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    # "noise and commotion": neither word is in the word list.
    body = client.post("/incident/classify", headers=headers, json={"text": "शोर शराबा"}).json()

    assert body["english_text"] == ""
    assert body["confidence"] == 0.0
    assert body["needs_review"] is True


def test_unsupported_language_code_is_rejected(client, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    response = client.post(
        "/incident/classify", headers=headers, json={"text": "bonjour", "language": "fr"}
    )

    assert response.status_code == 422


# ---------- new reports ----------


def test_hindi_report_stores_detected_language(client, db, users, text_model):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post("/incidents", headers=headers, json={"description": ROMANISED_THEFT}).json()

    assert body["language"] == "hi-Latn"
    assert body["category"]["code"] == "theft"
    assert body["severity"] == "HIGH"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "incident.reported"))
    assert audit.details["language"] == "hi-Latn"


def test_tourist_chosen_category_still_uses_translated_text_for_severity(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    body = client.post(
        "/incidents",
        headers=headers,
        json={"description": "होटल में आग लग गई", "category_code": "other"},
    ).json()

    assert body["severity"] == "CRITICAL"  # "आग" -> "fire" triggers the fire rule
