"""Loads the trained risk model made by `python -m ml.train_risk_model`.

Like the text model: ml/artefacts/risk_model/<version>/ plus a LATEST file. model.joblib is a
pickle, so only load artefacts produced by our own training script.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

from app.core.config import settings
from app.ml.risk_features import columns

VERSION_PATTERN = re.compile(r"riskmodel-v\d+-[0-9a-f]{10}")


class RiskModelUnavailable(Exception):
    """No trained risk model found (run `python -m ml.train_risk_model`)."""


@dataclass
class RiskModel:
    model: object
    metadata: dict

    @property
    def version(self) -> str:
        return self.metadata["model_version"]

    @property
    def cell_size_m(self) -> int:
        return self.metadata["cell_size_m"]

    def past_rate(self, cell_name: str) -> float:
        rates = self.metadata["cell_past_rates"]
        return rates.get(cell_name, self.metadata["default_past_rate"])

    def scores(self, all_features: np.ndarray) -> np.ndarray:
        """Calibrated scores in [0, 1] from the full feature matrix (FEATURE_NAMES order)."""
        selected = all_features[:, columns(self.metadata["feature_names"])]
        return self.model.predict_proba(selected)[:, 1]


@lru_cache(maxsize=1)
def _load(directory: str) -> RiskModel:
    root = Path(directory)
    latest = root / "LATEST"
    if not latest.is_file():
        raise RiskModelUnavailable("No trained risk model - run: python -m ml.train_risk_model")
    version = latest.read_text(encoding="utf-8").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise RiskModelUnavailable(f"Unexpected model version name: {version!r}")
    folder = root / version
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    return RiskModel(joblib.load(folder / "model.joblib"), metadata)


def get_risk_model() -> RiskModel:
    return _load(str(settings.risk_model_dir))


def reset_cache() -> None:
    _load.cache_clear()
