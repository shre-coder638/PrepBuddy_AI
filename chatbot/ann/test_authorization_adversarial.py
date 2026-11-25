import pytest

from chatbot.ann.authorization import authorize_evidence
from chatbot.ann.evidence import (
    is_valid_evidence,
    select_candidate_evidence,
)


RECORD = {
    "protocol_id": 14,
    "protocol": "MRI",
    "step_id": 301,
    "step": "Remove earrings",
    "instruction": "Remove earrings before the scan.",
    "similarity": 0.95,
}


@pytest.mark.parametrize("instruction", [
    "Remove watches. Do not remove earrings.",
    "Remove watches instead of earrings.",
    "Remove earrings only if approved by your doctor.",
    "Remove earrings unless advised otherwise.",
    "Remove earrings. Do not remove implanted devices.",
    "Do not remove earrings.",
    "Remove earrings if safe to do so.",
    "Remove other jewellery, not earrings.",
])
def test_unsafe_or_complex_removal_not_authorized(instruction):

    record = {
        **RECORD,
        "instruction": instruction,
    }

    assert not authorize_evidence(
        "Should I remove my earrings?",
        record,
        protocol_id=14,
    )


@pytest.mark.parametrize("instruction", [
    "Remove earrings before the scan.",
    "Please remove your earrings before the procedure.",
    "Remove earrings when instructed by staff.",
])
def test_narrow_stored_directive(instruction):

    assert authorize_evidence(
        "Should I remove my earrings?",
        {
            **RECORD,
            "instruction": instruction,
        },
        protocol_id=14,
    )


def test_exact_instruction_lookup():

    assert authorize_evidence(
        "Show me the Remove earrings step.",
        RECORD,
        protocol_id=14,
    )


def test_exact_lookup_selected():

    selected = select_candidate_evidence(
        "Show me the Remove earrings step.",
        [RECORD],
        protocol_id=14,
    )

    assert len(selected) == 1
    assert selected[0]["step_id"] == 301


@pytest.mark.parametrize("question", [
    "Tell me why I should remove earrings.",
    "Tell me whether I can ignore the Remove earrings step.",
    "Show me alternatives to the Remove earrings step.",
    "Tell me how to remove earrings from an infected ear.",
])
def test_partial_title_not_authorized(question):

    assert not authorize_evidence(
        question,
        RECORD,
        protocol_id=14,
    )


def test_boolean_protocol_identifier_rejected():

    assert not is_valid_evidence(
        {
            **RECORD,
            "protocol_id": True,
        },
        protocol_id=1,
    )


def test_cross_protocol_lookup_rejected():

    assert not authorize_evidence(
        "Show me the Remove earrings step.",
        RECORD,
        protocol_id=12,
    )
