"""Evidence-preserving response formatting for the ANN pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from .response_validator import validate_response

SAFE_FALLBACK = (
    "I couldn't confidently find an answer in the stored preparation "
    "instructions. Please check your official instructions or contact "
    "your clinical team."
)


def build_response(question: str, facts: Iterable[dict[str, object]]) -> str:
    """Format approved facts verbatim, or return the safe fallback."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    fact_texts = [
        fact.get("fact", fact.get("text"))
        for fact in facts
    ]
    usable = [fact.strip() for fact in fact_texts if isinstance(fact, str) and fact.strip()]
    if not usable:
        return SAFE_FALLBACK
    answer = "\n".join(usable)
    return answer if validate_response(answer, usable) else SAFE_FALLBACK
