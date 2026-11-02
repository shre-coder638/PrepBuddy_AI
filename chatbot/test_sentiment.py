import pytest

from chatbot.sentiment import analyze_patient_message


def test_anxious_patient_is_detected():
    result = analyze_patient_message("I'm really worried about tomorrow.")
    assert result["sentiment"] == "negative"
    assert result["emotion"] == "anxious"
    assert result["requires_human"] is False


def test_confused_patient_requests_clarification():
    result = analyze_patient_message("I'm confused. What does this mean?")
    assert result["emotion"] == "confused"
    assert result["intent"] == "clarification"


def test_distressed_message_is_flagged_for_human_review():
    result = analyze_patient_message("I feel overwhelmed and can't cope.")
    assert result["emotion"] == "distressed"
    assert result["requires_human"] is True


def test_clinical_concern_is_flagged():
    result = analyze_patient_message("I have chest pain.")
    assert result["intent"] == "clinical_concern"
    assert result["requires_human"] is True


def test_thanks_is_positive_acknowledgement():
    result = analyze_patient_message("Thank you, that was helpful.")
    assert result["sentiment"] == "positive"
    assert result["intent"] == "acknowledgement"


def test_plain_question_is_neutral_instruction_question():
    result = analyze_patient_message("When should I stop eating?")
    assert result["sentiment"] == "neutral"
    assert result["intent"] == "instruction_question"


def test_empty_message_rejected():
    with pytest.raises(ValueError):
        analyze_patient_message("  ")
