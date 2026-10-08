"""Severity rules, checked case by case against the rules written in the project brief.

These are unit tests, not an accuracy measurement: there is no independently labelled data.
"""

import pytest

from app.models.incident import Severity
from app.services.severity import assess_severity

H, C, M, L = Severity.HIGH, Severity.CRITICAL, Severity.MEDIUM, Severity.LOW

CASES = [
    # (text, category, expected) - the first one is the brief's own example
    ("My phone was stolen near the market", "theft", H),
    ("Someone stole my passport at the station", "theft", H),
    ("My wallet was taken from my bag", "theft", H),
    ("My umbrella was stolen from the cafe", "theft", M),  # minor theft
    ("My friend fell and is bleeding from the head", "accident", H),  # injury
    ("A man keeps following me", "harassment", H),
    ("I am alone and lost near the fort", "lost_person", H),  # alone
    ("I don't speak Hindi and nobody here understands me", "other", H),  # cannot communicate
    ("He has a knife and is threatening me", "harassment", C),  # threat to life
    ("My husband is unconscious on the floor", "medical_emergency", C),
    ("There is smoke and flames in the kitchen", "other", C),  # fire words
    ("Fire in the market", "fire", C),
    ("We are trapped in the lift", "other", C),
    ("My daughter is missing since this morning", "lost_person", C),  # missing child
    ("My friend has not come back to the hotel", "lost_person", M),  # missing adult
    ("There is an unattended bag at the gate", "suspicious_activity", L),
    ("The hotel overcharged me", "other", L),
    ("Something happened", None, M),  # unknown category
]


@pytest.mark.parametrize(("text", "category", "expected"), CASES)
def test_severity_rules(text, category, expected):
    assert assess_severity(text, category).severity == expected


def test_sos_is_always_critical():
    assert assess_severity("SOS", None, is_sos=True).severity == C


def test_high_risk_zone_raises_to_high():
    calm = assess_severity("There is an unattended bag", "suspicious_activity")
    in_zone = assess_severity(
        "There is an unattended bag", "suspicious_activity", in_high_risk_zone=True
    )

    assert (calm.severity, in_zone.severity) == (L, H)


def test_reasons_explain_the_result():
    result = assess_severity("My phone was stolen near the market", "theft")

    assert "HIGH: theft of a phone, passport, wallet or money" in result.reasons
    assert "MEDIUM: default for category 'theft'" in result.reasons


def test_curly_apostrophe_still_matches():
    # Phones often type ’ instead of '.
    assert assess_severity("I can’t speak the language", "other").severity == H


def test_known_limitation_negation_is_not_understood():
    # Keyword rules see "hurt" and raise the severity, although the sentence says nobody is
    # hurt. Documented limitation; an operator can lower the severity.
    result = assess_severity("Small collision, nobody is hurt", "accident")

    assert result.severity == H


def test_valuables_only_raise_theft():
    # "phone" in a lost-person report must not trigger the theft rule.
    assert assess_severity("I am lost and my phone battery is dead", "lost_person").severity == M
