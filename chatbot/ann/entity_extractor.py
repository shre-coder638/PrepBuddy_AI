"""Conservative extraction of entities useful for protocol retrieval."""

from __future__ import annotations

import re

ENTITY_PATTERNS = {
    "procedure": re.compile(r"\b(?:mri|ct|x[- ]?ray|ultrasound|scan|ecg|endoscopy)\b", re.I),
    "time": re.compile(r"\b(?:\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|midnight|noon)\b", re.I),
}


def extract_entities(text: str) -> dict[str, list[str]]:
    """Return matched entity strings without inferring medical information."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return {
        name: list(dict.fromkeys(match.group(0).casefold() for match in pattern.finditer(text)))
        for name, pattern in ENTITY_PATTERNS.items()
    }
