"""Loads the trained text classifier made by `python -m ml.train_text_classifier`.

The training script writes ml/artefacts/text_classifier/<version>/ and a LATEST file with the
version name. We load that version once and keep it in memory.

Security note: model.joblib is a Python pickle. Loading a pickle can run code, so only load
artefacts produced by our own training script - never files from an unknown source.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib

from app.core.config import settings

VERSION_PATTERN = re.compile(r"textclf-v\d+-[0-9a-f]{10}")


class ModelUnavailable(Exception):
    """No trained model found (run `python -m ml.train_text_classifier`)."""


@dataclass(frozen=True)
class Prediction:
    category_code: str
    confidence: float  # calibrated probability of the top category
    alternatives: list[tuple[str, float]]  # next most likely categories
    model_version: str


class TextClassifier:
    def __init__(self, model, metadata: dict) -> None:
        self.model = model
        self.metadata = metadata
        self.version: str = metadata["model_version"]
        self.languages: list[str] = metadata["languages"]

    def predict(self, text: str) -> Prediction:
        probabilities = self.model.predict_proba([text])[0]
        order = probabilities.argsort()[::-1]
        ranked = [(str(self.model.classes_[i]), float(probabilities[i])) for i in order]
        best_code, best_confidence = ranked[0]
        return Prediction(best_code, best_confidence, ranked[1:3], self.version)


@lru_cache(maxsize=1)
def _load(directory: str) -> TextClassifier:
    root = Path(directory)
    latest = root / "LATEST"
    if not latest.is_file():
        raise ModelUnavailable(
            "No trained text classifier - run: python -m ml.train_text_classifier"
        )
    version = latest.read_text(encoding="utf-8").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ModelUnavailable(f"Unexpected model version name: {version!r}")
    folder = root / version
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    return TextClassifier(joblib.load(folder / "model.joblib"), metadata)


def get_classifier() -> TextClassifier:
    return _load(str(settings.text_model_dir))


def reset_cache() -> None:
    """Forget the loaded model (used by tests, or after retraining)."""
    _load.cache_clear()
