"""Deterministic hashed bag-of-words embeddings with no optional dependency."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable

from .preprocessing import tokenize

DEFAULT_DIMENSION = 256


def _index(token: str, dimension: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimension


def embed(text: str, dimension: int = DEFAULT_DIMENSION) -> tuple[float, ...]:
    """Create a normalized, deterministic vector for one text."""
    if dimension < 1:
        raise ValueError("dimension must be positive")
    vector = [0.0] * dimension
    tokens = tokenize(text)
    for token in tokens:
        vector[_index(token, dimension)] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector) if norm else tuple(vector)


def embed_many(texts: Iterable[str], dimension: int = DEFAULT_DIMENSION) -> list[tuple[float, ...]]:
    """Create embeddings while preserving input order."""
    return [embed(text, dimension=dimension) for text in texts]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    """Return cosine similarity, safely handling empty or mismatched vectors."""
    left_values = tuple(left)
    right_values = tuple(right)
    if len(left_values) != len(right_values) or not left_values:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left_values, right_values)) / (
        left_norm * right_norm
    )
