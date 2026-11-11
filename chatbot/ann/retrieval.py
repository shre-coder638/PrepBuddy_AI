"""In-memory nearest-neighbor retrieval for approved text records."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from .embeddings import cosine_similarity, embed


@dataclass(frozen=True)
class RetrievalResult:
    record: dict[str, object]
    score: float


class Retriever:
    """Retrieve records by cosine similarity over deterministic embeddings."""

    def __init__(self, records: Iterable[dict[str, object]] = (), *, text_key: str = "text") -> None:
        self.text_key = text_key
        self._records: list[tuple[dict[str, object], tuple[float, ...]]] = []
        self.add(records)

    def add(self, records: Iterable[dict[str, object]]) -> None:
        for record in records:
            text = record.get(self.text_key)
            if isinstance(text, str) and text.strip():
                self._records.append((dict(record), embed(text)))

    def search(self, query: str, *, limit: int = 3, threshold: float = 0.0) -> list[RetrievalResult]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        query_vector = embed(query)
        ranked = [
            RetrievalResult(record, cosine_similarity(query_vector, vector))
            for record, vector in self._records
        ]
        return sorted(
            (result for result in ranked if result.score >= threshold),
            key=lambda result: result.score,
            reverse=True,
        )[:limit]
