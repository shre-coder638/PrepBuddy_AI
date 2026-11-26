"""Cloud-side ANN dispatch and independent evidence validation."""

import json
import logging

from django.conf import settings

from chatbot.rag import SAFE_FALLBACK, safety_response
from chatbot.response_generator import apply_communication_style

from .authorization import authorize_evidence
from .clarification import assess_clarification
from .multilingual_safety import multilingual_safety_response
from .preparation_intent import is_preparation_overview
from .protocol_overview import build_protocol_overview
from .protocol_records import load_protocol_records
from .remote_service import validate_payload
from .remote_client import request_remote_ann, RemoteANNError


logger = logging.getLogger(__name__)


HELP_PHRASES = {
    "hi",
    "hello",
    "hey",
    "hi prepbuddy",
    "hello prepbuddy",
    "hey prepbuddy",
    "help",
    "help me",
    "what can you help me with",
    "what can you do",
    "what do you do",
}


def fallback():
    return {
        "answer": SAFE_FALLBACK,
        "sources": [],
        "needs_clinical_team": True,
    }


def general_help():
    return {
        "answer": (
            "Hello! I'm PrepBuddy, your preparation-instructions "
            "assistant. I can help you understand the stored "
            "preparation instructions for your assigned procedure. "
            "For personal medical advice, contact your clinical team."
        ),
        "sources": [],
        "needs_clinical_team": False,
    }


def missing_protocol():
    return {
        "answer": (
            "I couldn't identify an assigned preparation protocol. "
            "Please confirm your procedure with your clinical team."
        ),
        "sources": [],
        "needs_clinical_team": True,
    }


def same_payload(left, right):
    # JSON comparison distinguishes booleans from integers
    # and rejects unexpected response fields.
    return json.dumps(
        left,
        sort_keys=True,
        allow_nan=False,
    ) == json.dumps(
        right,
        sort_keys=True,
        allow_nan=False,
    )


def validate_grounded_response(
    result,
    question,
    protocol_id,
    communication_style,
):
    if not isinstance(result, dict):
        raise RemoteANNError("Invalid response object.")

    # An abstention never permits remote clinical text.
    if result.get("sources") == []:
        return fallback()

    if set(result) != {
        "answer",
        "sources",
        "needs_clinical_team",
    }:
        raise RemoteANNError("Unexpected response fields.")

    if result["needs_clinical_team"] is not False:
        raise RemoteANNError("Invalid grounded response status.")

    sources = result["sources"]

    if not isinstance(sources, list) or len(sources) != 1:
        raise RemoteANNError("Expected one grounded instruction.")

    source = sources[0]

    if not isinstance(source, dict):
        raise RemoteANNError("Invalid evidence object.")

    if (
        type(source.get("protocol_id")) is not int
        or source["protocol_id"] != protocol_id
        or type(source.get("step_id")) is not int
        or source["step_id"] < 1
    ):
        raise RemoteANNError("Invalid evidence scope.")

    records = load_protocol_records(protocol_id)

    matches = [
        record for record in records
        if record["step_id"] == source["step_id"]
        and record["protocol_id"] == protocol_id
    ]

    if len(matches) != 1:
        raise RemoteANNError("Evidence is missing or ambiguous.")

    record = matches[0]

    name = record["protocol"].casefold()

    if (
        protocol_id == 16
        or "non-clinical" in name
        or "qa - " in name
    ):
        raise RemoteANNError("Protocol is not eligible.")

    if not authorize_evidence(
        question,
        record,
        protocol_id=protocol_id,
    ):
        raise RemoteANNError("Evidence authorization failed.")

    expected_source = {
        "protocol_id": record["protocol_id"],
        "protocol": record["protocol"],
        "step_id": record["step_id"],
        "step": record["step"],
        "minutes_before_procedure": record[
            "minutes_before_procedure"
        ],
        "is_critical": record["is_critical"],
    }

    expected_answer = apply_communication_style(
        f"Stored instruction - {record['step']}: "
        f"{record['instruction']}",
        communication_style,
    )

    expected = {
        "answer": expected_answer,
        "sources": [expected_source],
        "needs_clinical_team": False,
    }

    if not same_payload(result, expected):
        raise RemoteANNError(
            "Remote response differs from current stored evidence."
        )

    # Return locally reconstructed content.
    return expected


def answer_remote_ann(
    question,
    protocol_id=None,
    communication_style="neutral",
    requires_human=False,
):
    if (
        not getattr(settings, "STAGING_MODE", False)
        or getattr(settings, "CHATBOT_BACKEND", "") != "remote_ann"
    ):
        return fallback()

    try:
        if not isinstance(question, str) or not question.strip():
            return fallback()

        if type(requires_human) is not bool:
            return fallback()

        question = question.strip()

        # Preserve local clinical escalation even when
        # the remote neural network is unavailable.
        escalation = safety_response(
            question,
            requires_human=requires_human,
        )

        if escalation is None:
            escalation = multilingual_safety_response(question)

        if escalation is not None:
            return escalation

        normalized = " ".join(question.casefold().split())
        normalized = normalized.rstrip("?.!").strip()

        if normalized in HELP_PHRASES:
            return general_help()

        if type(protocol_id) is not int or protocol_id < 1:
            return missing_protocol()

        arguments = validate_payload({
            "question": question,
            "protocol_id": protocol_id,
            "communication_style": communication_style,
            "requires_human": requires_human,
        })

        question = arguments["question"]
        communication_style = arguments["communication_style"]

        if protocol_id == 16:
            return fallback()

        clarification = assess_clarification(
            question,
            history=None,
            active_protocol_id=protocol_id,
        )

        if clarification["required"]:
            return {
                "answer": clarification["message"],
                "sources": [],
                "needs_clinical_team": (
                    clarification["kind"] == "procedure_mismatch"
                ),
            }

        # Complete protocol overviews require no neural network.
        if is_preparation_overview(question):
            return build_protocol_overview(
                protocol_id,
                communication_style=communication_style,
            ) or fallback()

        result = request_remote_ann(
            url=getattr(settings, "REMOTE_ANN_URL", ""),
            token=getattr(settings, "ANN_SERVICE_TOKEN", ""),
            **arguments,
        )

        return validate_grounded_response(
            result,
            question,
            protocol_id,
            communication_style,
        )

    except Exception as exc:
        # Never log question content or service credentials.
        logger.warning(
            "Remote ANN backend failed safely: %s",
            type(exc).__name__,
        )

        return fallback()
