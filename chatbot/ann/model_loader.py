"""Load ANN training data from the package's JSON datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .intent_classifier import IntentClassifier


def load_json_dataset(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a JSON list of intent records."""
    dataset_path = Path(path)
    with dataset_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{dataset_path} must contain a JSON list")
    return [record for record in data if isinstance(record, dict)]


def load_intent_classifier(
    path: str | Path | None = None,
    *,
    threshold: float = 0.25,
) -> IntentClassifier:
    """Build a classifier from a dataset, defaulting to training data."""
    dataset_path = Path(path) if path else Path(__file__).parent.parent / "datasets" / "intent_training.json"
    return IntentClassifier(load_json_dataset(dataset_path), threshold=threshold)
