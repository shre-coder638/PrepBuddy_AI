"""Selection of approved facts from retrieved records."""

from __future__ import annotations

from collections.abc import Iterable

from .retrieval import RetrievalResult


def select_facts(results: Iterable[RetrievalResult], *, limit: int = 3) -> list[dict[str, object]]:
    """Return unique, high-scoring records without generating new facts."""
    if limit < 1:
        raise ValueError("limit must be positive")
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for result in results:
        fact = result.record.get("fact", result.record.get("text"))
        if not isinstance(fact, str) or not fact.strip() or fact in seen:
            continue
        seen.add(fact)
        selected.append({**result.record, "score": round(result.score, 6)})
        if len(selected) == limit:
            break
    return selected
