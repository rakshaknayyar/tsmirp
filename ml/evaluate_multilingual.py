"""Evaluate language detection and "translate, then classify" for Hindi and romanised Hindi.

Run from the repository root AFTER training the text model (fixed seed, same result each time):

    python -m ml.train_text_classifier
    python -m ml.evaluate_multilingual

What it measures (all on SYNTHETIC text):
1. Language detection accuracy for English, Hindi and romanised Hindi rows.
2. Category accuracy and macro-F1 for Hindi and romanised Hindi (reported SEPARATELY):
   - without translation (the English model reads the Hindi text directly), and
   - with the word-list translation (the way the app works).
3. A small hand-written check set of romanised Hindi with NEW wording. Its new words were
   deliberately NOT added to the word list, so it shows what happens with unseen vocabulary.
4. For comparison: English rows from unseen templates (the text model's own test split).

Why the main Hindi numbers are optimistic: the word list (app/ml/hindi_glossary.py) was
written while looking at the same Hindi templates, so it knows all their words.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from app.ml.language import detect_language
from app.ml.text_classifier import _load
from app.ml.translator import get_translator
from ml.text_data import CATEGORIES, generate_texts
from ml.train_text_classifier import (
    REVIEW_THRESHOLD,
    SEED,
    TEST_TEMPLATE_FRACTION,
    split_by_template,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "ml" / "artefacts" / "text_classifier"

# Hand-written romanised Hindi with wording that is NOT in the templates (2 per category).
# Written after the word list; their new words (jeb, behosh, bichhad, ...) were not added to it.
CHECK_SET = [
    ("Station par kisi ne meri jeb kaat li", "theft"),
    ("Mera wallet gayab hai, lagta hai kisi ne utha liya", "theft"),
    ("Ek ladka mujhe ghoor raha hai aur peeche aa raha hai", "harassment"),
    ("Dukaandaar ne mujhe galat tarike se chhua", "harassment"),
    ("Meri beti behosh ho gayi hai", "medical_emergency"),
    ("Mere pet mein bahut dard ho raha hai aur ulti aa rahi hai", "medical_emergency"),
    ("Hamari car ka accident ho gaya, sir mein chot lagi hai", "accident"),
    ("Seedhi se gir gaye, pair toot gaya lagta hai", "accident"),
    ("Mera beta mele mein kahin chala gaya", "lost_person"),
    ("Hum apne group se bichhad gaye hain", "lost_person"),
    ("Ek aadmi ATM ke paas sabko dekh raha hai", "suspicious_activity"),
    ("Gate ke paas ek ajeeb packet rakha hai", "suspicious_activity"),
    ("Zameen hil rahi thi, sab log bahar bhaag gaye", "natural_disaster"),
    ("Nadi ka paani sadak tak aa gaya hai", "natural_disaster"),
    ("Restaurant mein aag lag gayi, sab taraf dhuan hai", "fire"),
    ("Bijli ke taar se aag nikal rahi hai", "fire"),
    ("Hotel ne booking cancel kar di, ab kahan rukein?", "other"),
    ("Auto wale ne double kiraya le liya", "other"),
]


def latest_classifier():
    version = (MODEL_DIR / "LATEST").read_text(encoding="utf-8").strip()
    return _load(str(MODEL_DIR)), version


def score(classifier, texts: list[str], truth: list[str]) -> dict:
    probabilities = classifier.model.predict_proba(texts)
    predicted = list(classifier.model.classes_[probabilities.argmax(axis=1)])
    confidence = probabilities.max(axis=1)
    # Same rule as the app: an empty translation gets confidence 0 (always reviewed).
    confidence = np.where([t.strip() == "" for t in texts], 0.0, confidence)
    return {
        "n": len(texts),
        "accuracy": float(accuracy_score(truth, predicted)),
        "macro_f1": float(
            f1_score(truth, predicted, labels=CATEGORIES, average="macro", zero_division=0)
        ),
        "flagged_for_review": float((confidence < REVIEW_THRESHOLD).mean()),
    }


def translate_all(texts: list[str], language: str) -> tuple[list[str], float]:
    """English texts, and the share of rows where at least one word was unknown."""
    translator = get_translator()
    results = [translator.translate(t, language) for t in texts]
    return [r.text for r in results], float(np.mean([bool(r.unknown_words) for r in results]))


def evaluate() -> dict:
    classifier, version = latest_classifier()
    rows = generate_texts(SEED)
    english = [r for r in rows if r.language == "en"]
    _, english_test = split_by_template(english, TEST_TEMPLATE_FRACTION, SEED)

    detection = {
        language: float(
            np.mean([detect_language(r.text) == language for r in rows if r.language == language])
        )
        for language in ["en", "hi", "hi-Latn"]
    }
    results = {
        "en (unseen templates, no translation needed)": score(
            classifier, [r.text for r in english_test], [r.category for r in english_test]
        )
    }
    unknown_share = {}
    for language in ["hi", "hi-Latn"]:
        subset = [r for r in rows if r.language == language]
        texts, truth = [r.text for r in subset], [r.category for r in subset]
        results[f"{language} without translation"] = score(classifier, texts, truth)
        translated, unknown_share[language] = translate_all(texts, language)
        results[f"{language} with word-list translation"] = score(classifier, translated, truth)

    check_texts, check_truth = [t for t, _ in CHECK_SET], [c for _, c in CHECK_SET]
    check_translated, unknown_share["check set"] = translate_all(check_texts, "hi-Latn")
    results["hi-Latn check set (new wording), with translation"] = score(
        classifier, check_translated, check_truth
    )
    check_detection = float(np.mean([detect_language(t) == "hi-Latn" for t in check_texts]))
    examples = [
        (text, translated, str(classifier.model.predict([translated])[0]), truth)
        for (text, truth), translated in zip(CHECK_SET, check_translated, strict=True)
    ]
    return {
        "text_model_version": version,
        "translator": get_translator().method,
        "seed": SEED,
        "detection": detection,
        "check_set_detection": check_detection,
        "results": results,
        "unknown_word_share": unknown_share,
        "check_examples": examples,
    }


def write_report(path: Path, r: dict) -> None:
    lines = [
        "# Multilingual evaluation (SYNTHETIC data)",
        "",
        "> Measured on **synthetic, template-generated** text plus a tiny hand-written check set.",
        "> These numbers do **not** show real-world accuracy. Regenerate with",
        "> `python -m ml.evaluate_multilingual` (after `python -m ml.train_text_classifier`).",
        "",
        f"- Text model: `{r['text_model_version']}` (trained on English only)",
        f"- Translator: `{r['translator']}` (word-by-word lookup in app/ml/hindi_glossary.py)",
        f"- Seed: {r['seed']}; review threshold: confidence < {REVIEW_THRESHOLD}",
        "",
        "## Language detection",
        "",
        "| Language | Rows detected correctly |",
        "|---|---|",
        *[f"| {lang} | {acc:.3f} |" for lang, acc in r["detection"].items()],
        f"| hi-Latn check set | {r['check_set_detection']:.3f} |",
        "",
        "## Classification",
        "",
        "| Rows | n | Accuracy | Macro-F1 | Flagged for review |",
        "|---|---|---|---|---|",
        *[
            f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['macro_f1']:.3f} | "
            f"{m['flagged_for_review']:.3f} |"
            for name, m in r["results"].items()
        ],
        "",
        "Share of rows with at least one word not in the word list: "
        + ", ".join(f"{k} {v:.3f}" for k, v in r["unknown_word_share"].items()),
        "",
        "## Check set: what the classifier actually read",
        "",
        "| Romanised Hindi | English given to the model | Predicted | True |",
        "|---|---|---|---|",
        *[f"| {t} | {e or '(nothing)'} | {p} | {c} |" for t, e, p, c in r["check_examples"]],
        "",
        "## How to read this",
        "",
        "- The Hindi and romanised Hindi template rows are an OPTIMISTIC upper bound: the word "
        "list was written while looking at those templates.",
        "- The check set has only 18 sentences (2 per category), so its accuracy is very "
        "uncertain; it mainly shows that new words are lost and how that hurts.",
        "- 'Without translation' shows why the translation step is needed at all.",
        "",
        "## Known limitations",
        "",
        "- Word-by-word lookup ignores grammar and word order; unknown Hindi words are lost "
        "(in romanised Hindi they are kept as they are, which only helps if they are English).",
        "- Only the vocabulary of the demo is covered. A real system would use a proper "
        "translation model behind the same Translator interface.",
        "- Mixed-language messages and spelling variants (e.g. 'chori' vs 'chorii') are only "
        "partly handled.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not (MODEL_DIR / "LATEST").is_file():
        sys.exit("No text model - run: python -m ml.train_text_classifier")
    result = evaluate()
    report = REPO_ROOT / "ml" / "reports" / "multilingual.md"
    write_report(report, result)
    for name, m in result["results"].items():
        print(f"{name}: accuracy {m['accuracy']:.3f}, macro-F1 {m['macro_f1']:.3f}")
    print(f"Report: {report.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
