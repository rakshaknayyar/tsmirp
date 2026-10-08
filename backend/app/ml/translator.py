"""Translation step: Hindi / romanised Hindi -> English, so the English-only text classifier
and the English severity keywords can be used ("translate, then classify").

The rest of the app only uses the Translator INTERFACE (one method, translate). Today there is
one implementation, WordListTranslator: a word-by-word lookup in a hand-written word list
(app/ml/hindi_glossary.py). It runs offline, costs nothing and is easy to explain, but its
output is a list of English keywords, not a proper sentence, and words that are not in the list
are lost. A real translation service could be added later as another class with the same
translate() method, without changing the classifier or the API.
"""

import unicodedata
from dataclasses import dataclass, field
from typing import Protocol

from app.ml.hindi_glossary import (
    DEVANAGARI,
    DEVANAGARI_STOP_WORDS,
    ROMANISED,
    ROMANISED_STOP_WORDS,
)
from app.ml.language import tokens

MAX_PHRASE_WORDS = 3


@dataclass(frozen=True)
class Translation:
    text: str  # the English text
    source_language: str  # "hi" or "hi-Latn"
    method: str  # which translator produced it
    known_words: int  # words or phrases found in the word list
    # Words not in the word list. In romanised Hindi these are kept if they look English.
    unknown_words: list[str] = field(default_factory=list)


class Translator(Protocol):
    def translate(self, text: str, source_language: str) -> Translation: ...


def _normalise(word: str) -> str:
    return unicodedata.normalize("NFC", word).lower()


class WordListTranslator:
    method = "wordlist-v1"

    def __init__(self) -> None:
        # Normalised once here, so the word list can be typed in any Unicode form.
        self.tables = {
            language: (
                {_normalise(k): v for k, v in table.items()},
                {_normalise(w) for w in stop_words},
            )
            for language, table, stop_words in [
                ("hi", DEVANAGARI, DEVANAGARI_STOP_WORDS),
                ("hi-Latn", ROMANISED, ROMANISED_STOP_WORDS),
            ]
        }

    def translate(self, text: str, source_language: str) -> Translation:
        if source_language not in self.tables:
            raise ValueError(f"Cannot translate from {source_language!r}")
        table, stop_words = self.tables[source_language]
        words = [_normalise(t) for t in tokens(text)]
        english: list[str] = []
        unknown: list[str] = []
        known = 0
        i = 0
        while i < len(words):
            # Try the longest phrase first: 3 words, then 2, then 1.
            for size in range(min(MAX_PHRASE_WORDS, len(words) - i), 0, -1):
                phrase = " ".join(words[i : i + size])
                if phrase in table:
                    if table[phrase]:
                        english.append(table[phrase])
                    known += 1
                    i += size
                    break
            else:
                word = words[i]
                if word in stop_words:
                    pass  # grammar word: drop it
                elif source_language == "hi-Latn" and word.isascii():
                    english.append(word)  # probably English already ("phone", "hotel")
                    unknown.append(word)
                else:
                    unknown.append(word)  # a Hindi word we do not know: lost
                i += 1
        return Translation(" ".join(english), source_language, self.method, known, unknown)


_translator: Translator = WordListTranslator()


def get_translator() -> Translator:
    return _translator
