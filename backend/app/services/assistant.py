"""The tourist assistant: picks the best answer from a fixed knowledge base.

How it works (no AI text generation, so it can never invent facts or phone numbers):
1. Turn the question into English (detect language, translate Hindi word by word).
2. Score every topic in app/services/assistant_kb.py: one point per keyword found in the
   question (whole words only).
3. Return the topic with the most points; on a tie the topic higher in the list wins. If no
   keyword matches, return a fallback answer.
The emergency numbers 112 and 1363 are always included. Questions are not stored.
"""

import re
from dataclasses import dataclass

from app.services.assistant_kb import EMERGENCY_LINE, FALLBACK_ANSWER, TOPICS, Topic
from app.services.language import prepare_text


@dataclass(frozen=True)
class AssistantAnswer:
    topic: Topic | None  # None = no topic matched (fallback answer)
    answer: str
    language: str
    english_question: str
    emergency: str = EMERGENCY_LINE


def _score(topic: Topic, question: str) -> int:
    return sum(
        bool(re.search(r"\b" + re.escape(keyword) + r"\b", question)) for keyword in topic.keywords
    )


def answer_question(question: str) -> AssistantAnswer:
    prepared = prepare_text(question)
    english = prepared.text_for_rules.lower()
    best: Topic | None = None
    best_score = 0
    for topic in TOPICS:
        score = _score(topic, english)
        if score > best_score:  # ">" keeps the earlier topic on a tie
            best, best_score = topic, score
    return AssistantAnswer(
        topic=best,
        answer=best.answer if best else FALLBACK_ANSWER,
        language=prepared.language,
        english_question=prepared.english,
    )
