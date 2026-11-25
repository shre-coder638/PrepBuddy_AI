
"""Conservative multilingual entity extraction for protocol retrieval."""

from __future__ import annotations

import re

# Each alias maps to a canonical procedure name and its protocol ID.
PROCEDURE_ALIASES = {
    11: {
        "name": "colonoscopy",
        "patterns": [
            r"\bcolonoscopy\b",
            r"\bendoscopy\b",
            r"कोलोनोस्कोपी",
            r"एंडोस्कोपी",
        ],
    },
    12: {
        "name": "ct",
        "patterns": [
            r"\bct\b",
            r"\bcomputed tomography\b",
            r"सीटी\s*(?:स्कैन|की\s*(?:appointment|अपॉइंटमेंट|जाँच|जांच|रिपोर्ट)|करवाना|करवानी|करवाने|कराने)",
        ],
    },
    9: {
        "name": "ecg",
        "patterns": [
            r"\becg\b",
            r"\belectrocardiogram\b",
            r"ईसीजी",
        ],
    },
    13: {
        "name": "x-ray",
        "patterns": [
            r"\bx\s*-\s*ray\b",
            r"\bxray\b",
            r"एक्स\s*-?\s*रे",
        ],
    },
    14: {
        "name": "mri",
        "patterns": [
            r"\bmri\b",
            r"\bmagnetic resonance imaging\b",
            r"एमआरआई",
        ],
    },
}

COMPILED_PROCEDURE_PATTERNS = {
    protocol_id: [
        re.compile(pattern, re.IGNORECASE)
        for pattern in definition["patterns"]
    ]
    for protocol_id, definition in PROCEDURE_ALIASES.items()
}

TIME_PATTERN = re.compile(
    r"\b(?:\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|midnight|noon)\b",
    re.IGNORECASE,
)


def extract_entities(text: str) -> dict[str, object]:
    """Extract explicit procedure and time mentions without inference."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    detected_ids = []
    detected_names = []

    for protocol_id, patterns in COMPILED_PROCEDURE_PATTERNS.items():
        if any(pattern.search(text) for pattern in patterns):
            detected_ids.append(protocol_id)
            detected_names.append(
                PROCEDURE_ALIASES[protocol_id]["name"]
            )

    candidates = sorted(detected_ids)

    return {
        "procedure": detected_names,
        "procedure_id": candidates[0] if len(candidates) == 1 else None,
        "procedure_candidates": candidates,
        "time": list(
            dict.fromkeys(
                match.group(0).casefold()
                for match in TIME_PATTERN.finditer(text)
            )
        ),
    }
