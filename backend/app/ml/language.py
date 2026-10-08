"""Simple language detection for incident reports: "en", "hi" or "hi-Latn".

Rules (no ML model, so it is easy to explain and test):
1. If at least half of the letters are Devanagari (Unicode block U+0900-U+097F) -> "hi".
2. Otherwise, count the words that are typical romanised Hindi ("mera", "hai", "chori" ...,
   taken from app/ml/hindi_glossary.py). At least 2 such words, making up at least a quarter
   of all words -> "hi-Latn" (Hindi typed in English letters).
3. Otherwise -> "en".
Mixed or very short messages can be detected wrongly; ml/evaluate_multilingual.py measures
how often this happens on the SYNTHETIC texts.
"""

import re
import unicodedata

from app.ml.hindi_glossary import ROMANISED, ROMANISED_STOP_WORDS

LANGUAGES = ("en", "hi", "hi-Latn")

# Romanised Hindi words that are also common English words, so they do not count as evidence.
ENGLISH_LOOKALIKES = {"me", "the", "to", "he", "main", "par", "pe", "log", "papa", "mummy"}
ROMANISED_MARKERS = (
    {key for key in ROMANISED if " " not in key} | ROMANISED_STOP_WORDS
) - ENGLISH_LOOKALIKES

# A "token" is a run of characters that are not spaces or punctuation. (Python's \w would
# split Devanagari words, because vowel signs are not counted as word characters.)
TOKEN = re.compile(r"[^\s.,!?;:()\"'\-।]+")


def tokens(text: str) -> list[str]:
    # NFC makes letters with a dot (nukta), like ज़, look the same however they were typed.
    return TOKEN.findall(unicodedata.normalize("NFC", text))


def is_devanagari(char: str) -> bool:
    return "\u0900" <= char <= "\u097f"


def detect_language(text: str) -> str:
    letters = [c for c in text if c.isalpha() or is_devanagari(c)]
    if letters and sum(is_devanagari(c) for c in letters) / len(letters) >= 0.5:
        return "hi"
    words = [t.lower() for t in tokens(text)]
    hits = sum(w in ROMANISED_MARKERS for w in words)
    if hits >= 2 and hits >= 0.25 * len(words):
        return "hi-Latn"
    return "en"
