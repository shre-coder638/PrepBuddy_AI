"""Validation rules preventing responses from exceeding retrieved evidence."""

from __future__ import annotations

import re
from collections.abc import Iterable

NUMBER_PATTERN = re.compile(r"\b\d+(?:[:.]\d+)?\b")


def validate_response(response: str, facts: Iterable[str]) -> bool:
    """Allow a response only when it is non-empty and introduces no numbers."""
    if not isinstance(response, str) or not response.strip():
        return False
    approved_numbers = set(NUMBER_PATTERN.findall("\n".join(facts)))
    response_numbers = set(NUMBER_PATTERN.findall(response))
    return response_numbers.issubset(approved_numbers)
