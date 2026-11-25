"""Experimental multilingual temporal-intent detection.

This module is diagnostic only. It does not alter production retrieval,
clinical safety routing, or patient-facing responses.
"""

from __future__ import annotations

import re


RESULTS_PATTERNS = [
    r"\b(?:when|how)\s+(?:will|can)\s+i\s+(?:get|receive|see)\s+(?:my\s+)?(?:mri\s+)?(?:results?|report|findings)\b",
    r"\b(?:results?|report|findings)\s+(?:when|kab)\s+(?:will\s+i\s+)?(?:be\s+available|come|arrive|get|mile(?:ga|gi|nge)?)\b",
    r"\b(?:scan\s+results?|test\s+results?)\b",
    r"\b(?:when|how)\s+(?:will|can)\s+i\s+(?:get|receive|see)\s+(?:my\s+)?(?:mri\s+)?results?\b",
    r"(?:रिपोर्ट|रिजल्ट|नतीजे|परिणाम).{0,30}(?:कब|कब\s+तक|मिलेगा|मिलेगी|मिलेंगे|आएगा|आएगी)",
    r"(?:कब|कब\s+तक).{0,30}(?:रिपोर्ट|रिजल्ट|नतीजे|परिणाम)",
    r"\b(?:report|result|findings)\s+(?:kab|kaise)\s+(?:milegi|milega|milenge|aayegi|aayega)\b",
    r"\b(?:mujhe|humein|humko)\s+(?:report|result)\s+(?:kab|kaise)\s+(?:milegi|milega|milenge)\b",
    r"\b(?:whom|who)\s+should\s+i\s+ask\b.{0,100}\b(?:when|how)\b.{0,80}\b(?:get|receive|see)\s+(?:my\s+)?results?\b",
    r"\bresults?\s+kab\s+aur\s+kaise\s+mil(?:e|ega|egi|enge)\b",
    r"\bwho\s+can\s+tell\s+me\b.{0,100}\b(?:when|how)\b.{0,100}\b(?:results?|report|findings)\b",
    r"\bhow\s+long\b.{0,100}\b(?:mri|scan|test)?\s*(?:results?|report|findings)\b.{0,80}\b(?:available|ready)\b",
    r"\b(?:mri|scan)\s+report\s+kitne\s+din\s+mein\s+(?:ready|available)\s+hogi\b",
    r"\bwhen\s+(?:will|can)\s+i\s+(?:get|receive|see)\s+(?:(?:my|the)\s+)?(?:mri\s+)?(?:results?|report|findings)\b",
    r"\b(?:mri\s+)?(?:report|results?|findings)\s+(?:mujhe\s+)?(?:kab|when)\s+(?:milegi|milega|milenge|available\s+(?:hogi|hoga|honge|hongi)|ready\s+(?:hogi|hoga|honge|hongi))\b",
    r"\bwho\s+can\s+tell\s+me\b.{0,100}\b(?:mri\s+)?(?:results?|report|findings)\s+(?:kab|when)\s+(?:ready|available)\s+(?:honge|hongi|hoga|hogi)\b",
]

DURING_SCAN_PATTERNS = [
    r"\b(?:during|while)\s+(?:the\s+)?(?:mri|scan|scanning)\b",
    r"\b(?:inside|in)\s+(?:the\s+)?(?:mri\s+)?scanner\b",
    r"\b(?:when|if)\s+i(?:'m| am)?\s+(?:inside|in)\s+(?:the\s+)?scanner\b",
    r"\b(?:what\s+happens|what\s+should\s+i\s+do)\s+(?:during|inside)\s+(?:(?:the|my)\s+)?(?:mri|scan|scanning|scanner)\b",
    r"(\u0938\u094d\u0915\u0948\u0928|\u090f\u092e\u0906\u0930\u0906\u0908).{0,20}(?:\u0915\u0947\s+\u0926\u094c\u0930\u093e\u0928|\u0915\u0947\s+\u0938\u092e\u092f)",
    r"(?:दौरान|समय).{0,20}(?:स्कैन|एमआरआई)",
    r"\b(?:scan|scanning|mri)\s+ke\s+(?:dauran|time)\b",
    r"\bscanner\s+(?:mein|ke\s+andar)\b",
    r"\bscan\s+ke\s+darmiyan\b",
    r"\u091c\u093e\u0902\u091a\s+\u0915\u0947\s+(?:\u0926\u094c\u0930\u093e\u0928|\u0938\u092e\u092f)",
]

POST_SCAN_PATTERNS = [
    r"\b(?:i\s+have\s+)?(?:finished|completed)\s+(?:my\s+)?(?:mri|scan)\b.{0,120}\b(?:before\s+leaving|before\s+i\s+leave)\b",
    r"\b(?:the\s+)?(?:mri|scan)\s+is\s+(?:over|complete|completed|finished)\b.{0,120}\b(?:go\s+home|take\s+me\s+home|leave|drive)\b",
    r"\b(?:i\s+)?(?:completed|finished)\s+(?:the\s+)?(?:mri|scan)\b.{0,120}\b(?:take\s+me\s+home|go\s+home|leave|drive)\b",
    r"\b(?:mera|meri)\s+(?:mri|scan)\s+(?:complete|khatam)\s+ho\s+gaya\b.{0,100}\b(?:department\s+se\s+)?nikalne\s+se\s+pehle\b",
    r"(?:\u090f\u092e\u0906\u0930\u0906\u0908|\u0938\u094d\u0915\u0948\u0928).{0,40}\u0939\u094b \u0917\u092f\u093e \u0939\u0948.{0,100}\u0935\u093f\u092d\u093e\u0917 \u0938\u0947 \u0928\u093f\u0915\u0932\u0928\u0947 \u0938\u0947 \u092a\u0939\u0932\u0947",


    r"\bafter\s+(?:my\s+)?scan\s+(?:can|should|may)\s+i\b",
    r"\b(?:leave|go\s+home|drive|resume)\s+after\s+(?:the\s+)?(?:mri|scan)\b",
    r"(\u0938\u094d\u0915\u0948\u0928|\u090f\u092e\u0906\u0930\u0906\u0908).{0,20}(?:\u0915\u0947\s+\u092c\u093e\u0926|\u0939\u094b\u0928\u0947\s+\u0915\u0947\s+\u092c\u093e\u0926)",
    r"(?:\u0915\u0947\s+\u092c\u093e\u0926|\u092c\u093e\u0926\s+\u092e\u0947\u0902).{0,20}(\u0938\u094d\u0915\u0948\u0928|\u090f\u092e\u0906\u0930\u0906\u0908)",
    r"\b(?:scan|mri)\s+ke\s+baad\b.{0,50}\b(?:ghar|home|drive|gaadi|kaam|office|activity|resume)\b",
    r"\bscan\s+(?:khatam|complete|finish)\s+(?:hone\s+)?ke\s+baad\b",
    r"\b(?:scan|mri)\s+(?:khatam|complete|finish)\s+ho\s+gaya\b.{0,80}\b(?:ghar\s+jaa?\s+sakta|go\s+home)\b",
    r"(?:\u090f\u092e\u0906\u0930\u0906\u0908|\u0938\u094d\u0915\u0948\u0928).{0,30}(?:\u092a\u0942\u0930\u0940|\u092a\u0942\u0930\u093e|\u0916\u0924\u094d\u092e).{0,20}(?:\u0939\u094b \u0917\u0908|\u0939\u094b \u0917\u092f\u093e|\u0939\u0941\u0906).{0,50}(?:\u0918\u0930|\u091c\u093e).{0,20}\u091c\u093e \u0938\u0915\u0924\u093e",
    r"\b(?:ghar|home)\s+(?:kab|kaise)\s+(?:ja\s+sakta|jaa\s+sakta|ja\s+sakta)\b",
    r"\bafter\s+(?:my\s+)?scan\b.{0,60}\b(?:can|should|may)\s+i\s+(?:return\s+to\s+work|go\s+back\s+to\s+work)\b",
    r"\bcan\s+i\s+(?:drive|go)\s+(?:home|back)\s+after\s+(?:(?:the|my)\s+)?(?:mri|scan)\b",
    r"\b(?:i\s+)?(?:completed|finished)\s+(?:(?:the|my)\s+)?(?:mri|scan)\b.{0,120}\b(?:take\s+me\s+home|go\s+home|leave|drive)\b",
    r"\b(?:mri|scan)\s+(?:complete|completed)\s+ho\s+gaya\b.{0,80}\bdepartment\s+se\s+leave\s+kar\s+sakta\b",
]


def _compile(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


COMPILED_PATTERNS = {
    "results_followup": _compile(RESULTS_PATTERNS),
    "during_scan": _compile(DURING_SCAN_PATTERNS),
    "post_scan_discharge": _compile(POST_SCAN_PATTERNS),
}


def detect_temporal_intent(text: str) -> str | None:
    """Return one explicit temporal intent, or None if unknown/ambiguous."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    normalized = " ".join(text.casefold().split())
    if not normalized:
        return None

    matches = [
        intent
        for intent, patterns in COMPILED_PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    ]

    return matches[0] if len(matches) == 1 else None
