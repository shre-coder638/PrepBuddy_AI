"""Detect explicit requests for a general preparation overview."""

from __future__ import annotations

import re


OVERVIEW_PATTERNS = (
    r"what should i do to prepare for my procedure",
    r"what should i do before my procedure",
    r"how should i prepare for my procedure",
    r"how do i prepare for my procedure",
    r"how can i prepare for my procedure",
    r"what are my preparation steps",
    r"show me my preparation instructions",
    r"show me my preparation steps",
    r"give me my preparation instructions",
    r"what are my preparation instructions",
    r"how should i prepare",
    r"how do i prepare",
    r"preparation instructions",
    r"preparation steps",

    # Hinglish
    r"procedure se pehle kya karna chahiye",
    r"test se pehle kya karna chahiye",
    r"scan se pehle kya karna chahiye",
    r"taiyari kaise karun",
    r"tayari kaise karun",
    r"mujhe kya taiyari karni chahiye",

    # Hindi: ASCII-safe Unicode escapes.
    r"\u092e\u0941\u091d\u0947 \u0915\u094d\u092f\u093e \u0924\u0948\u092f\u093e\u0930\u0940 \u0915\u0930\u0928\u0940 \u091a\u093e\u0939\u093f\u090f",
    r"\u0924\u0948\u092f\u093e\u0930\u0940 \u0915\u0948\u0938\u0947 \u0915\u0930\u0942\u0902",
)

COMPILED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in OVERVIEW_PATTERNS
)


def is_preparation_overview(question: str) -> bool:
    """Recognize explicit general preparation requests."""
    if not isinstance(question, str):
        raise TypeError("question must be a string")

    normalized = " ".join(question.casefold().split())
    normalized = normalized.rstrip("?.!").strip()

    if not normalized:
        return False

    return any(
        pattern.fullmatch(normalized)
        for pattern in COMPILED_PATTERNS
    )
