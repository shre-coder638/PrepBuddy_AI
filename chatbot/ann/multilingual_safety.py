"""Additional conservative multilingual clinical safety safeguards."""

import re
import unicodedata


HINDI_CLINICAL_TERMS = (
    "\u0926\u0935\u093e",  # Medication
    "\u0917\u094b\u0932\u0940",  # Tablet
    "\u0907\u0902\u0938\u0941\u0932\u093f\u0928",  # Insulin
    "\u0917\u0930\u094d\u092d",  # Pregnancy
    "\u092a\u094d\u0930\u0947\u0917\u094d\u0928\u0947\u0902\u091f",
    "\u090f\u0932\u0930\u094d\u091c\u0940",  # Allergy
    "\u0930\u0915\u094d\u0924\u0938\u094d\u0930\u093e\u0935",
    "\u0916\u0942\u0928 \u092c\u0939",  # Bleeding
    "\u0926\u0930\u094d\u0926",  # Pain
    "\u091a\u0915\u094d\u0915\u0930",  # Dizziness
    "\u0909\u0932\u094d\u091f\u0940",  # Vomiting
    "\u092e\u0927\u0941\u092e\u0947\u0939",  # Diabetes
    "\u0936\u0941\u0917\u0930",
    "\u092c\u0941\u0916\u093e\u0930",  # Fever
    "\u092c\u0947\u0939\u094b\u0936",  # Unconsciousness
)


HINGLISH_CLINICAL_PATTERN = re.compile(
    r"\b(?:"
    r"dawa|dawai|dava|davai|dawaa|dawayein|"
    r"goli|goliyan|goliy[ao]n|"
    r"garbhavati|garbhvati|garbhawati|"
    r"dard|chakkar|ulti|bukhar|"
    r"behosh|behoshi|"
    r"khoon\s+(?:aa|bah)\w*"
    r")\b"
)


HINDI_URGENT_TERMS = (
    "\u0938\u093e\u0902\u0938 \u0928\u0939\u0940\u0902",
    "\u0938\u093e\u0901\u0938 \u0928\u0939\u0940\u0902",
    "\u0938\u0940\u0928\u0947 \u092e\u0947\u0902 "
    "\u0926\u0930\u094d\u0926",
)


HINGLISH_URGENT_PATTERN = re.compile(
    r"\b(?:"
    r"s[aa]+ns\s+nahi\w*\s+aa\w*|"
    r"seene\s+me(?:in)?\s+dard|"
    r"saans\s+lene\s+me(?:in)?\s+"
    r"(?:takleef|dikkat|mushkil)"
    r")\b"
)


CLINICAL_RESPONSE = (
    "Your question may require individual medical guidance. "
    "Please contact your clinical team before changing your "
    "medication or preparation instructions. "
    "I cannot safely make that decision for you."
)


URGENT_RESPONSE = (
    "If you are currently experiencing chest pain, severe "
    "breathing difficulty or another medical emergency, "
    "seek emergency medical help immediately. "
    "Do not wait for a chatbot response. "
    "For preparation-related concerns, contact your clinical team."
)


def multilingual_safety_response(question):

    if not isinstance(question, str):
        return None

    normalized = unicodedata.normalize(
        "NFKC", question
    ).casefold()

    normalized = " ".join(normalized.split())

    urgent = (
        any(
            term in normalized
            for term in HINDI_URGENT_TERMS
        )
        or HINGLISH_URGENT_PATTERN.search(normalized)
    )

    if urgent:
        return {
            "answer": URGENT_RESPONSE,
            "sources": [],
            "needs_clinical_team": True,
        }

    clinical = (
        any(
            term in normalized
            for term in HINDI_CLINICAL_TERMS
        )
        or HINGLISH_CLINICAL_PATTERN.search(normalized)
    )

    if clinical:
        return {
            "answer": CLINICAL_RESPONSE,
            "sources": [],
            "needs_clinical_team": True,
        }

    return None
