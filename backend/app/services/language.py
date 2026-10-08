"""Turn a tourist's message into English before classification, severity rules or the
assistant look at it.

    detect the language (or use the one the client gave) -> translate if it is not English

Used by app/services/classification.py, app/services/incidents.py, app/api/classify.py and
app/services/assistant.py.
"""

from dataclasses import dataclass

from app.ml.language import detect_language
from app.ml.translator import Translation, get_translator


@dataclass(frozen=True)
class PreparedText:
    original: str
    language: str  # "en", "hi" or "hi-Latn"
    language_detected: bool  # False if the client said which language it is
    english: str  # the original if English, otherwise the translation
    translation: Translation | None  # None for English

    @property
    def understood_nothing(self) -> bool:
        """The translation produced no English words at all (e.g. Hindi words that are all
        missing from the word list)."""
        return self.translation is not None and not self.english.strip()

    @property
    def text_for_rules(self) -> str:
        """Original + English, so English keyword rules also see English words in a mixed
        message (e.g. "phone" in "Mera phone chori ho gaya")."""
        if self.translation is None:
            return self.original
        return f"{self.original} {self.english}"


def prepare_text(text: str, language: str | None = None) -> PreparedText:
    detected = language is None
    language = language or detect_language(text)
    if language == "en":
        return PreparedText(text, language, detected, text, None)
    translation = get_translator().translate(text, language)
    return PreparedText(text, language, detected, translation.text, translation)
