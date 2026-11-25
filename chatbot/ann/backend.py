"""Configured ANN backend with optional structured telemetry."""

import logging
import time

from django.conf import settings

from chatbot.rag import SAFE_FALLBACK

from .pipeline import answer_with_ann
from .experience_service import record_experience


logger = logging.getLogger(__name__)

BACKEND_VERSION = "e5-pipeline-v1"


def fallback():
    return {
        "answer": SAFE_FALLBACK,
        "sources": [],
        "needs_clinical_team": True,
    }


def answer_configured_ann(
    question,
    protocol_id=None,
    communication_style="neutral",
    requires_human=False,
    history=None,
):

    if getattr(settings, "CHATBOT_BACKEND", "rag") != "ann":

        logger.error("Invalid ANN backend configuration.")
        return fallback()

    started = time.perf_counter()

    trace = {
        "outcome": "abstention",
        "retrieved_step_ids": [],
    }

    try:

        result = answer_with_ann(
            question,
            protocol_id=protocol_id,
            communication_style=communication_style,
            requires_human=requires_human,
            history=history,
            trace=trace,
        )

    except Exception as exc:

        logger.error(
            "ANN backend failure: %s",
            type(exc).__name__,
        )

        trace["outcome"] = "error"
        result = fallback()

    if getattr(settings, "ANN_RECORD_EXPERIENCES", False):

        try:

            valid_protocol = (
                protocol_id
                if type(protocol_id) is int and protocol_id > 0
                else None
            )

            returned = [
                source["step_id"]
                for source in result.get("sources", [])
            ]

            record_experience(
                protocol_id=valid_protocol,
                model_version=BACKEND_VERSION,
                outcome=trace["outcome"],
                retrieved_step_ids=trace["retrieved_step_ids"],
                returned_step_ids=returned,
                needs_clinical_team=result.get(
                    "needs_clinical_team",
                    False,
                ),
                latency_ms=round(
                    (time.perf_counter() - started) * 1000
                ),
            )

        except Exception as exc:

            # Telemetry failure must not change the answer.
            logger.warning(
                "ANN experience recording failed: %s",
                type(exc).__name__,
            )

    return result
