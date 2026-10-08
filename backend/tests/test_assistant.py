"""Phase 8: the tourist assistant (POST /assistant/query) and its knowledge base."""

import re

import pytest

from app.models.user import Role
from app.services.assistant import answer_question
from app.services.assistant_kb import EMERGENCY_LINE, FALLBACK_ANSWER, TOPICS
from tests.conftest import auth_headers

ALLOWED_NUMBERS = {"112", "1363"}


def test_knowledge_base_contains_no_other_phone_numbers():
    """The assistant must never invent numbers: only 112 and 1363 may appear anywhere."""
    texts = [EMERGENCY_LINE, FALLBACK_ANSWER]
    for topic in TOPICS:
        texts += [topic.title, topic.answer, *topic.keywords]

    numbers = {n for text in texts for n in re.findall(r"\d[\d -]{1,}\d", text)}

    assert numbers <= ALLOWED_NUMBERS
    assert {"112", "1363"} <= set(re.findall(r"\d+", EMERGENCY_LINE))


def test_topic_ids_are_unique():
    assert len({t.id for t in TOPICS}) == len(TOPICS)


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("My passport is lost, what do I do?", "passport"),
        ("Someone stole my wallet", "theft"),
        ("A man is following me", "harassment"),
        ("I need a doctor, I have a fever", "medical"),
        ("I cannot find my child", "lost"),
        ("There is smoke in the corridor", "fire"),
        ("The taxi driver overcharged me", "scam"),
        ("How does the SOS button work?", "sos"),
        ("Is this area dangerous?", "risk"),
        ("Who can see my location?", "privacy"),
        ("mera phone chori ho gaya", "theft"),  # romanised Hindi, translated first
        ("होटल में आग लग गई", "fire"),  # Hindi, translated first
    ],
)
def test_questions_find_the_right_topic(question, topic):
    result = answer_question(question)

    assert result.topic is not None and result.topic.id == topic


def test_unknown_question_gets_fallback_with_emergency_numbers():
    result = answer_question("What time does the museum open?")

    assert result.topic is None
    assert result.answer == FALLBACK_ANSWER
    assert "112" in result.emergency and "1363" in result.emergency


def test_tie_goes_to_the_more_urgent_topic():
    # "fire" (fire topic) and "taxi" (scam topic) score one point each: fire is listed first.
    assert answer_question("My taxi is on fire").topic.id == "fire"


def test_endpoint_answers_with_emergency_numbers(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    response = client.post(
        "/assistant/query", headers=headers, json={"question": "Mera passport kho gaya"}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["topic"], body["language"]) == ("passport", "hi-Latn")
    assert body["emergency"] == EMERGENCY_LINE
    assert "hand-written" in body["note"]


def test_endpoint_rules(client, users):
    headers = auth_headers(client, users[Role.TOURIST])

    assert client.post("/assistant/query", json={"question": "help"}).status_code == 401
    for question in ["", "a" * 501]:  # too short, too long
        response = client.post("/assistant/query", headers=headers, json={"question": question})
        assert response.status_code == 422
