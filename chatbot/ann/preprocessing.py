"""Shared text normalization used by the lightweight ANN components."""

from __future__ import annotations

import re
from collections.abc import Iterable

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")


def normalize_text(text: str) -> str:
    """Return normalized text and reject non-text input explicitly."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return " ".join(text.casefold().split())


def tokenize(text: str) -> list[str]:
    """Tokenize patient text without removing clinically meaningful words."""
    return TOKEN_PATTERN.findall(normalize_text(text))


def token_set(text: str) -> set[str]:
    """Return unique normalized tokens for overlap-based matching."""
    return set(tokenize(text))


def text_from_examples(examples: Iterable[dict[str, object]]) -> list[str]:
    """Extract non-empty text fields from intent examples."""
    texts = []
    for example in examples:
        text = example.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return texts
