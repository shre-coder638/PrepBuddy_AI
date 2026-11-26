"""Unified, source-grounded ANN preparation assistant pipeline."""

from __future__ import annotations

import logging

from chatbot.rag import SAFE_FALLBACK, safety_response

from chatbot.response_generator import apply_communication_style

from .authorization import authorize_evidence
from .multilingual_safety import multilingual_safety_response
from .clarification import assess_clarification
from .e5_retrieval import retrieve_e5_steps
from .evidence import select_candidate_evidence
from .preparation_intent import is_preparation_overview
from .protocol_overview import build_protocol_overview


logger = logging.getLogger(__name__)


def _fallback():
    return {
        "answer": SAFE_FALLBACK,
        "sources": [],
        "needs_clinical_team": True,
    }


def answer_with_ann(
    question,
    protocol_id=None,
    communication_style="neutral",
    requires_human=False,
    history=None,
    trace=None,
    *,
    corpus_records=None,
):
    """
    Run the protocol-scoped ANN preparation assistant.

    Return stored instructions only when authorized by the
    evidence selection safeguards. Otherwise, abstain.

    When corpus_records is supplied, retrieval and overview
    generation use only those records without database access.
    """
    if trace is None:
        trace = {}

    trace.update(
        outcome="abstention",
        retrieved_step_ids=[],
    )

    if not isinstance(question, str) or not question.strip():
        return _fallback()

    question = question.strip()

    escalation = safety_response(
        question,
        requires_human=requires_human,
    )

    if escalation is None:
        escalation = multilingual_safety_response(question)

    if escalation is not None:
        trace["outcome"] = "escalation"
        return escalation

    normalized = " ".join(question.casefold().split())
    normalized = normalized.rstrip("?.!").strip()

    help_phrases = {
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

    if normalized in help_phrases:
        trace["outcome"] = "general_help"
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

    if (
        not isinstance(protocol_id, int)
        or isinstance(protocol_id, bool)
        or protocol_id < 1
    ):
        return {
            "answer": (
                "I couldn't identify an assigned preparation protocol. "
                "Please confirm your procedure with your clinical team."
            ),
            "sources": [],
            "needs_clinical_team": True,
        }

    # Temporary exclusion of the existing non-clinical QA protocol.
    # Replace with explicit publication metadata before deployment.
    if protocol_id == 16:
        return _fallback()

    clarification = assess_clarification(
        question,
        history=history,
        active_protocol_id=protocol_id,
    )

    if clarification["required"]:
        trace["outcome"] = "clarification"
        return {
            "answer": clarification["message"],
            "sources": [],
            "needs_clinical_team": (
                clarification["kind"] == "procedure_mismatch"
            ),
        }

    corpus_kwargs = (
        {}
        if corpus_records is None
        else {"corpus_records": corpus_records}
    )

    if is_preparation_overview(question):
        try:
            overview = build_protocol_overview(
                protocol_id,
                communication_style=communication_style,
                **corpus_kwargs,
            )

            if overview is None:
                return _fallback()

            logger.info(
                "ANN protocol overview completed: protocol=%s steps=%s",
                protocol_id,
                len(overview["sources"]),
            )

            trace["outcome"] = "overview"
            return overview

        except Exception as exc:
            trace["outcome"] = "error"
            logger.error(
                "ANN protocol overview failed: %s",
                type(exc).__name__,
            )
            return _fallback()

    try:
        records = retrieve_e5_steps(
            question,
            protocol_id=protocol_id,
            limit=10,
            **corpus_kwargs,
        )

        trace["retrieved_step_ids"] = list(dict.fromkeys(
            record["step_id"]
            for record in records
            if isinstance(record, dict)
            and record.get("protocol_id") == protocol_id
            and type(record.get("step_id")) is int
            and record["step_id"] > 0
        ))

        candidates = select_candidate_evidence(
            question,
            records,
            protocol_id=protocol_id,
            limit=3,
        )

        logger.info(
            "ANN retrieval completed: protocol=%s retrieved=%s "
            "candidates=%s",
            protocol_id,
            len(records),
            len(candidates),
        )

        authorized = [
            record
            for record in candidates
            if authorize_evidence(
                question,
                record,
                protocol_id=protocol_id,
            )
        ]

        if not authorized:
            return _fallback()

        # Do not select arbitrarily between multiple matching
        # instructions that may contain different conditions.
        if len(authorized) != 1:
            return _fallback()

        source = authorized[0]
        trace["outcome"] = "grounded"

        answer = (
            f"Stored instruction - {source['step']}: "
            f"{source['instruction']}"
        )

        answer = apply_communication_style(
            answer,
            communication_style,
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "protocol_id": source["protocol_id"],
                    "protocol": source["protocol"],
                    "step_id": source["step_id"],
                    "step": source["step"],
                    "minutes_before_procedure": source.get(
                        "minutes_before_procedure"
                    ),
                    "is_critical": source.get("is_critical"),
                }
            ],
            "needs_clinical_team": False,
        }

    except Exception as exc:
        trace["outcome"] = "error"
        logger.error(
            "ANN retrieval failed: %s",
            type(exc).__name__,
        )
        return _fallback()
