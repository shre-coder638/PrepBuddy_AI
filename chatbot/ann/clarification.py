"""Deterministic clarification decisions before preparation retrieval."""

import re
import unicodedata

from chatbot.ann.entity_extractor import extract_entities


OBJECT_REFERENCE_PATTERNS = (
    r"\b(?:it|these|those)\b",
    r"\b(?:remove|wear|carry|bring|keep|take\s+off|leave|put\s+away)\s+(?:this|that)\b",
    r"\b(?:what\s+about|how\s+about)\s+(?:this|that)\b",
    r"\b(?:isko|isey|isse|yeh|ye|woh|usko|use)\b",
)

HINDI_REFERENCE_TERMS = (
    "\u0907\u0938\u0947",       # ???
    "\u0907\u0938\u0915\u094b", # ????
    "\u0907\u0938\u0915\u093e", # ????
    "\u0907\u0938\u0915\u0940", # ????
    "\u092f\u0939",             # ??
    "\u092f\u0947",             # ??
    "\u0909\u0938\u0915\u094b", # ????
    "\u0909\u0938\u0947",       # ???
    "\u0935\u0939",             # ??
    "\u0935\u094b",             # ??
)

OBJECT_MENTION_PATTERNS = (
    r"\b(?:earrings?|jewellery|jewelry|necklace|watch|ring|"
    r"bracelet|patch|hearing aids?|implant|pacemaker|"
    r"metal|device|clothing|belt|keys|phone|"
    r"earphones?|headphones?|chain|pendant)\b",
)

HINDI_OBJECT_TERMS = (
    "\u091a\u0947\u0928",
    "\u0905\u0902\u0917\u0942\u0920\u0940",
    "\u0915\u093e\u0928 \u0915\u0940 \u092c\u093e\u0932\u0940",
    "\u0917\u0939\u0928\u0947",
    "\u0918\u0921\u093c\u0940",
    "\u092a\u0948\u091a",
    "\u0907\u092e\u094d\u092a\u094d\u0932\u093e\u0902\u091f",
)

ACKNOWLEDGEMENT_RE = re.compile(
    r"^(?:thank you|thanks)"
    r"(?:[\s,!.]+(?:that|this)\s+(?:was|is)\s+"
    r"(?:helpful|clear|useful))?[.! ]*$",
    re.IGNORECASE,
)

OBJECT_REFERENCE_RE = re.compile(
    "|".join(f"(?:{pattern})" for pattern in OBJECT_REFERENCE_PATTERNS),
    re.IGNORECASE,
)

OBJECT_MENTION_RE = re.compile(
    "|".join(f"(?:{pattern})" for pattern in OBJECT_MENTION_PATTERNS),
    re.IGNORECASE,
)


def _patient_messages(history):
    """Return non-empty patient messages only."""
    messages = []

    for message in history or []:
        if getattr(message, "role", None) != "patient":
            continue

        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            messages.append(content.strip())

    return messages


def _contains_hindi_term(text, terms):
    """Match Hindi terms without matching inside larger Devanagari words."""
    for term in terms:
        start = 0

        while True:
            index = text.find(term, start)
            if index == -1:
                break

            end = index + len(term)

            before_is_word = (
                index > 0
                and unicodedata.category(text[index - 1])[0] in ("L", "M", "N")
            )
            after_is_word = (
                end < len(text)
                and unicodedata.category(text[end])[0] in ("L", "M", "N")
            )

            if not before_is_word and not after_is_word:
                return True

            start = index + 1

    return False


def _has_object_reference(text):
    if OBJECT_REFERENCE_RE.search(text):
        return True

    return _contains_hindi_term(text, HINDI_REFERENCE_TERMS)


def _has_object_mention(text):
    if OBJECT_MENTION_RE.search(text):
        return True

    return _contains_hindi_term(text, HINDI_OBJECT_TERMS)


def assess_clarification(question, history=None, active_protocol_id=None):
    """
    Decide whether retrieval needs procedure or object clarification.

    Returns:
        {"required": False, "kind": None, "message": None}
        or a structured clarification decision.

    Assistant messages are deliberately excluded when resolving objects.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    current = question.strip()
    entities = extract_entities(current)
    candidates = entities["procedure_candidates"]

    if len(candidates) > 1:
        return {
            "required": True,
            "kind": "procedure",
            "message": (
                "I noticed more than one test mentioned. "
                "Which test are you asking about?"
            ),
        }

    if len(candidates) == 1:
        procedure_id = candidates[0]

        if (
            active_protocol_id is not None
            and procedure_id != active_protocol_id
        ):
            return {
                "required": True,
                "kind": "procedure_mismatch",
                "message": (
                    "The procedure you mentioned does not match "
                    "the preparation protocol assigned to you. "
                    "Please confirm your procedure with your clinical "
                    "team before following preparation instructions."
                ),
            }
    else:
        procedure_id = active_protocol_id

    patient_messages = _patient_messages(history)
    latest_patient_text = patient_messages[-1] if patient_messages else ""

    if procedure_id is None:
        return {
            "required": True,
            "kind": "procedure",
            "message": (
                "Which test are you preparing for—CT, ECG, X-ray, "
                "MRI, or colonoscopy/endoscopy?"
            ),
        }

    # An explicit object in the current message needs no object clarification.
    if _has_object_mention(current):
        return {
            "required": False,
            "kind": None,
            "message": None,
        }

    # Acknowledgements are not requests to identify a physical object.
    if ACKNOWLEDGEMENT_RE.fullmatch(current):
        return {
            "required": False,
            "kind": None,
            "message": None,
        }

    # Resolve pronouns only from the most recent patient message.
    # Older mentions may refer to an unrelated topic.
    if _has_object_reference(current) and not _has_object_mention(
        latest_patient_text
    ):
        return {
            "required": True,
            "kind": "object",
            "message": (
                "Which item are you referring to? Please tell me its name "
                "so I can check the relevant preparation instruction."
            ),
        }

    return {
        "required": False,
        "kind": None,
        "message": None,
    }
