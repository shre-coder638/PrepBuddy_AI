"""Lightweight patient-message tone and intent classification.

This is a communication aid, not a clinical triage or diagnostic system.
It deliberately does not generate medical advice.
"""
import re

POSITIVE = {
    "thank", "thanks", "thank you", "great", "good", "okay", "ok",
    "understand", "helpful", "appreciate", "fine",
}
NEGATIVE = {
    "bad", "upset", "angry", "frustrated", "worried", "scared",
    "afraid", "confused", "anxious", "stress", "stressed", "pain",
    "problem", "issue", "not understand", "don't understand",
    "do not understand", "terrible", "unhappy",
}
ANXIOUS = {
    "worried", "scared", "afraid", "anxious", "nervous", "panic",
    "stress", "stressed", "frightened",
}
CONFUSED = {
    "confused", "don't understand", "do not understand", "unclear",
    "what does this mean", "explain again", "not sure",
}
FRUSTRATED = {
    "frustrated", "angry", "annoyed", "upset", "fed up",
}
DISTRESSED = {
    "can't cope", "cannot cope", "overwhelmed", "terrified",
    "hopeless", "desperate",
}
CLINICAL_REVIEW = {
    "chest pain", "difficulty breathing", "shortness of breath",
    "bleeding", "faint", "fainted", "severe pain", "allergic reaction",
    "side effect", "change my medication", "stop my medication",
    "missed my dose", "overdose", "fever", "vomiting",
}

def _contains(text, phrases):
    return any(phrase in text for phrase in phrases)

def analyze_patient_message(message):
    """Return deterministic sentiment/emotion/intent labels and flags."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")

    text = re.sub(r"\s+", " ", message.lower()).strip()

    positive = _contains(text, POSITIVE)
    negative = _contains(text, NEGATIVE)
    if positive and not negative:
        sentiment = "positive"
    elif negative:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    if _contains(text, DISTRESSED):
        emotion = "distressed"
    elif _contains(text, ANXIOUS):
        emotion = "anxious"
    elif _contains(text, CONFUSED):
        emotion = "confused"
    elif _contains(text, FRUSTRATED):
        emotion = "frustrated"
    else:
        emotion = "calm"

    if _contains(text, CLINICAL_REVIEW):
        intent = "clinical_concern"
    elif any(term in text for term in ("when", "what time", "how long", "before")):
        intent = "instruction_question"
    elif any(term in text for term in ("explain", "mean", "clarify", "confused")):
        intent = "clarification"
    elif any(term in text for term in ("thank", "thanks", "okay", "ok")):
        intent = "acknowledgement"
    elif any(term in text for term in ("help", "please", "can you")):
        intent = "help_request"
    else:
        intent = "other"

    requires_human = intent == "clinical_concern" or emotion == "distressed"

    # Heuristic confidence is intentionally conservative and not a
    # calibrated probability.
    confidence = 0.65 if sentiment != "neutral" or emotion != "calm" else 0.55

    return {
        "sentiment": sentiment,
        "emotion": emotion,
        "intent": intent,
        "confidence": confidence,
        "requires_human": requires_human,
        "model_version": "rules-v1",
    }
