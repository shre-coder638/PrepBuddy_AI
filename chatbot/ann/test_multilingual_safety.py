from unittest.mock import patch

import pytest

from chatbot.ann.multilingual_safety import (
    multilingual_safety_response,
    URGENT_RESPONSE,
)

from chatbot.ann.pipeline import answer_with_ann


@pytest.mark.parametrize("question", [
    "\u0926\u0935\u093e \u092c\u0902\u0926 "
    "\u0915\u0930 \u0926\u0942\u0902?",

    "\u0917\u0930\u094d\u092d\u0935\u0924\u0940",

    "\u0907\u0902\u0938\u0941\u0932\u093f\u0928",

    "\u090f\u0932\u0930\u094d\u091c\u0940",

    "\u0916\u0942\u0928 \u092c\u0939",

    "Kya main apni dawa band kar dun?",

    "Mujhe chakkar aa raha hai.",

    "Kya mujhe goli leni chahiye?",

    "Mujhe ulti ho rahi hai.",

    "Kya garbhavati hone par scan kara sakti hun?",
])
def test_multilingual_clinical_escalation(question):

    result = multilingual_safety_response(question)

    assert result is not None
    assert result["needs_clinical_team"] is True
    assert result["sources"] == []


@pytest.mark.parametrize("question", [
    "Mujhe seene mein dard ho raha hai.",
    "Mujhe saans nahi aa rahi.",
    "Saans lene mein dikkat hai.",

    "\u0938\u0940\u0928\u0947 \u092e\u0947\u0902 "
    "\u0926\u0930\u094d\u0926",
])
def test_potential_emergency(question):

    result = multilingual_safety_response(question)

    assert result["answer"] == URGENT_RESPONSE
    assert result["needs_clinical_team"] is True
    assert result["sources"] == []


@pytest.mark.parametrize("question", [
    "Taiyari kaise karun?",
    "MRI ke liye kapde kaise pehnu?",
    "Kya mujhe jewellery hatani hai?",
    "When should I arrive?",

    "\u0924\u0948\u092f\u093e\u0930\u0940 "
    "\u0915\u0948\u0938\u0947 "
    "\u0915\u0930\u0942\u0902",
])
def test_routine_question_not_intercepted(question):

    assert multilingual_safety_response(question) is None


def test_multilingual_safety_precedes_retrieval():

    with patch(
        "chatbot.ann.pipeline.retrieve_e5_steps",
    ) as retrieval:

        result = answer_with_ann(
            "Kya main apni dawa band kar dun?",
            protocol_id=14,
        )

    assert result["needs_clinical_team"] is True
    assert result["sources"] == []

    retrieval.assert_not_called()
