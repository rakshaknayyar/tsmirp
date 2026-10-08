"""Rule-based severity: LOW < MEDIUM < HIGH < CRITICAL.

Every rule that matches adds a reason; the final severity is the HIGHEST level among them.
Rules (from the project brief):
- Theft of a phone / passport / wallet-type item -> HIGH; other ("minor") theft -> MEDIUM.
- Injury, harassment, a tourist who is alone or cannot communicate, or a location inside a
  HIGH/CRITICAL risk zone -> HIGH.
- Threat to life, unconscious person, fire, someone trapped, a missing child, or any SOS ->
  CRITICAL (until an operator downgrades it).
Category defaults (when no rule above applies) are an assumption of this prototype:
  suspicious activity / other -> LOW; theft / accident / lost person / unknown -> MEDIUM;
  harassment / medical emergency / natural disaster -> HIGH; fire -> CRITICAL.

Limitations: simple English keyword matching (Hindi is translated first, Phase 8). It can be
fooled, e.g. "burning pain" counts as fire. Operators can always override the severity.
No accuracy figure is claimed: there is no independently labelled data. The rules are
checked by unit tests against the cases written in the brief.
"""

import re
from dataclasses import dataclass, field

from app.models.incident import Severity

ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

CATEGORY_DEFAULTS = {
    "theft": Severity.MEDIUM,
    "harassment": Severity.HIGH,
    "medical_emergency": Severity.HIGH,
    "accident": Severity.MEDIUM,
    "lost_person": Severity.MEDIUM,
    "suspicious_activity": Severity.LOW,
    "natural_disaster": Severity.HIGH,
    "fire": Severity.CRITICAL,
    "other": Severity.LOW,
}


def _words(*phrases: str) -> re.Pattern:
    """A pattern that matches any of the phrases as whole words (case-insensitive)."""
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in phrases) + r")\b", re.IGNORECASE)


VALUABLES = _words(
    "phone",
    "mobile",
    "smartphone",
    "passport",
    "wallet",
    "purse",
    "cash",
    "money",
    "credit card",
    "debit card",
    "bank card",
)
INJURY = _words(
    "injured",
    "injury",
    "injuries",
    "hurt",
    "bleeding",
    "blood",
    "broken bone",
    "broke my",
    "fracture",
    "fractured",
    "wound",
    "wounded",
)
ALONE_OR_CANNOT_COMMUNICATE = _words(
    "alone",
    "by myself",
    "on my own",
    "can't speak",
    "cannot speak",
    "can not speak",
    "don't speak",
    "do not speak",
    "can't communicate",
    "cannot communicate",
    "no one understands",
)
THREAT_TO_LIFE = _words(
    "kill",
    "killed",
    "killing",
    "gun",
    "knife",
    "weapon",
    "shoot",
    "shot",
    "stab",
    "stabbed",
    "my life is in danger",
    "going to die",
)
UNCONSCIOUS = _words(
    "unconscious",
    "unresponsive",
    "not responding",
    "not breathing",
    "no pulse",
    "passed out",
)
FIRE = _words("fire", "flames", "on fire", "burning", "blaze")
TRAPPED = _words(
    "trapped",
    "stuck inside",
    "locked inside",
    "locked in",
    "buried",
    "cannot get out",
    "can't get out",
)
CHILD = _words(
    "child",
    "children",
    "kid",
    "baby",
    "son",
    "daughter",
    "little brother",
    "little sister",
    "boy",
    "girl",
)


@dataclass
class SeverityAssessment:
    severity: Severity
    reasons: list[str] = field(default_factory=list)


def assess_severity(
    text: str,
    category_code: str | None,
    *,
    in_high_risk_zone: bool = False,
    is_sos: bool = False,
) -> SeverityAssessment:
    # Curly apostrophes (common on phones) become straight ones so "can’t" matches "can't".
    text = text.replace("’", "'")
    findings: list[tuple[Severity, str]] = []

    default = CATEGORY_DEFAULTS.get(category_code or "", Severity.MEDIUM)
    findings.append((default, f"default for category '{category_code or 'unknown'}'"))

    if is_sos:
        findings.append((Severity.CRITICAL, "SOS (stays CRITICAL until an operator downgrades)"))
    if category_code == "theft" and VALUABLES.search(text):
        findings.append((Severity.HIGH, "theft of a phone, passport, wallet or money"))
    if INJURY.search(text):
        findings.append((Severity.HIGH, "someone is injured"))
    if category_code == "harassment":
        findings.append((Severity.HIGH, "harassment"))
    if ALONE_OR_CANNOT_COMMUNICATE.search(text):
        findings.append((Severity.HIGH, "tourist is alone or cannot communicate"))
    if in_high_risk_zone:
        findings.append((Severity.HIGH, "location is inside a HIGH or CRITICAL risk zone"))
    if THREAT_TO_LIFE.search(text):
        findings.append((Severity.CRITICAL, "threat to life (weapon or threat to kill)"))
    if UNCONSCIOUS.search(text):
        findings.append((Severity.CRITICAL, "someone is unconscious or not breathing"))
    if category_code == "fire" or FIRE.search(text):
        findings.append((Severity.CRITICAL, "fire"))
    if TRAPPED.search(text):
        findings.append((Severity.CRITICAL, "someone is trapped"))
    if category_code == "lost_person" and CHILD.search(text):
        findings.append((Severity.CRITICAL, "missing child"))

    severity = max((level for level, _ in findings), key=ORDER.index)
    reasons = [f"{level.value}: {reason}" for level, reason in findings]
    return SeverityAssessment(severity=severity, reasons=reasons)
