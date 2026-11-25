"""Exact stored-instruction lookup without clinical interpretation."""

import re
import unicodedata


def normalize_text(value):

    return " ".join(
        unicodedata.normalize(
            "NFKC", value
        ).casefold().split()
    ).rstrip("?.!").strip()


def is_exact_instruction_lookup(question, record):

    if not isinstance(question, str):
        return False

    if not isinstance(record, dict):
        return False

    title = record.get("step")

    if not isinstance(title, str) or not title.strip():
        return False

    question = normalize_text(question)
    title = normalize_text(title)

    pattern = (
        r"(?:repeat|show me|tell me|read me)\s+"
        r"(?:the\s+)?"
        + re.escape(title)
        + r"(?:\s+(?:step|instruction|instructions))?"
    )

    return re.fullmatch(pattern, question) is not None
