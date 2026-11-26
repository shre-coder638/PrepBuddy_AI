"""Conservative evidence selection for protocol-scoped ANN retrieval."""

from __future__ import annotations

import math
from collections.abc import Iterable

from .explicit_lookup import is_exact_instruction_lookup

from chatbot.rag import (
    _has_explicit_concept_match,
    _is_explicit_step_lookup,
)


def is_valid_stored_evidence(record, protocol_id):
    """Check record integrity and assigned-protocol isolation."""
    if not isinstance(record, dict):
        return False

    if (
        not isinstance(protocol_id, int)
        or isinstance(protocol_id, bool)
        or protocol_id < 1
    ):
        return False

    if (
        type(record.get("protocol_id")) is not int
        or record["protocol_id"] != protocol_id
    ):
        return False

    step_id = record.get("step_id")

    if (
        not isinstance(step_id, int)
        or isinstance(step_id, bool)
        or step_id < 1
    ):
        return False

    for field in ("protocol", "step", "instruction"):
        value = record.get(field)

        if not isinstance(value, str) or not value.strip():
            return False

    if record["instruction"].strip().lower() in {
        ".", "-", "n/a"
    }:
        return False

    return True


def is_valid_evidence(record, protocol_id):
    """Validate ranked evidence including retrieval metadata."""
    if not is_valid_stored_evidence(record, protocol_id):
        return False

    score = record.get("similarity")

    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not math.isfinite(score)
        or not -1.000001 <= score <= 1.000001
    ):
        return False

    return True


def select_candidate_evidence(
    question: str,
    records: Iterable[dict],
    *,
    protocol_id: int,
    limit: int = 3,
) -> list[dict]:
    """
    Select structurally valid, protocol-scoped relevance candidates.

    These candidates require further relevance and safety validation
    before being returned to a patient.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
    ):
        raise ValueError("limit must be a positive integer")

    if (
        not isinstance(protocol_id, int)
        or isinstance(protocol_id, bool)
        or protocol_id < 1
    ):
        raise ValueError("protocol_id must be a positive integer")

    selected = []
    seen = set()

    for record in records:
        if not is_valid_evidence(record, protocol_id):
            continue

        step_id = record["step_id"]

        if step_id in seen:
            continue

        relevant = (
            is_exact_instruction_lookup(question, record)
            or _has_explicit_concept_match(question, record)
            or _is_explicit_step_lookup(question, record)
        )

        if not relevant:
            continue

        selected.append(dict(record))
        seen.add(step_id)

        if len(selected) == limit:
            break

    return selected
