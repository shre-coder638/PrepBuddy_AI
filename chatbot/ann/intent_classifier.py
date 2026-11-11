"""Small, deterministic intent classifier for routing chatbot requests."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from .embeddings import cosine_similarity, embed
from .preprocessing import normalize_text


@dataclass(frozen=True)
class IntentResult:
    """Classification result with a confidence score in the range [0, 1]."""

    intent: str
    confidence: float


class IntentClassifier:
    """Classify text by nearest example embedding."""

    def __init__(
        self,
        examples: Iterable[dict[str, object]] = (),
        *,
        dimension: int = 256,
        threshold: float = 0.25,
    ) -> None:
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        self.dimension = dimension
        self.threshold = threshold
        self._examples: list[tuple[str, tuple[float, ...]]] = []
        self.fit(examples)

    def fit(self, examples: Iterable[dict[str, object]]) -> None:
        """Replace training examples, ignoring malformed records explicitly."""
        fitted: list[tuple[str, tuple[float, ...]]] = []
        for example in examples:
            intent = example.get("intent")
            text = example.get("text")
            if not isinstance(intent, str) or not intent.strip():
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            fitted.append((intent.strip(), embed(text, self.dimension)))
        self._examples = fitted

    def predict(self, text: str) -> IntentResult:
        """Return the nearest intent or ``unknown`` below the confidence floor."""
        normalized = normalize_text(text)
        if not normalized or not self._examples:
            return IntentResult("unknown", 0.0)
        vector = embed(normalized, self.dimension)
        intent, score = max(
            ((intent, cosine_similarity(vector, example_vector))
             for intent, example_vector in self._examples),
            key=lambda item: item[1],
        )
        return IntentResult(
            intent if score >= self.threshold else "unknown",
            round(score, 6),
        )
