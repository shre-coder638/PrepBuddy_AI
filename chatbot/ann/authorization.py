"""Conservative authorization of retrieved preparation evidence."""

from __future__ import annotations

import re

from .evidence import is_valid_evidence
from .explicit_lookup import is_exact_instruction_lookup


UNSUPPORTED_REQUEST = re.compile(
    r"\b(?:why|what if|what happens if|side effects?|"
    r"dangerous|consequences?|risks?|safe for me|"
    r"already|accidentally|forgot|missed|instead)\b",
    re.IGNORECASE,
)

ITEM_TERMS = (
    r"jewellery|jewelry|earrings?|rings?|"
    r"necklaces?|bracelets?|watches?"
)

REMOVAL_REQUEST = re.compile(
    rf"(?:should|must|do) i (?:need to )?"
    rf"(?:remove|take off) (?:my |the )?"
    rf"(?:{ITEM_TERMS})",
    re.IGNORECASE,
)


def authorize_evidence(question, record, *, protocol_id):
    """Authorize narrowly supported instruction lookups."""

    if not isinstance(question, str) or not question.strip():
        return False

    if not is_valid_evidence(record, protocol_id):
        return False

    normalized = " ".join(question.casefold().split())
    normalized = normalized.rstrip("?.!").strip()

    if UNSUPPORTED_REQUEST.search(normalized):
        return False

    instruction = record["instruction"].strip()

    removal_match = REMOVAL_REQUEST.fullmatch(normalized)

    if removal_match:

        requested_item = removal_match.group(0).split()[-1]

        # Permit only a narrow, complete stored directive.
        # Never infer authorization from an item mentioned
        # somewhere in a different or contradictory clause.

        direct_pattern = (
            r"(?:please\s+)?(?:remove|take off)\s+"
            r"(?:your\s+|the\s+)?"
            + re.escape(requested_item)
            + r"(?:\s+before\s+(?:the|your)\s+"
              r"(?:scan|procedure|test)"
              r"|\s+when\s+instructed\s+by\s+staff)?"
            + r"\.?"
        )

        return bool(
            re.fullmatch(
                direct_pattern,
                instruction,
                flags=re.IGNORECASE,
            )
        )

    if is_exact_instruction_lookup(question, record):
        return True

    return False
