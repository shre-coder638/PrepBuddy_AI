"""Evaluate the complete ANN answering pipeline on development data."""

from __future__ import annotations

import os
import json
import time
import statistics

from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from unittest.mock import patch


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

import django
django.setup()

from chatbot.ann import pipeline
from chatbot.rag import SAFE_FALLBACK


ROOT = Path(__file__).resolve().parent

DATASET = ROOT / "multilingual_dev_questions.json"

RESULTS = ROOT / "results"


def evidence_key(record):
    return (
        record.get("protocol_id"),
        record.get("step_id"),
    )


def evaluate_question(row):

    trace = {
        "retrieved": [],
        "selected": [],
        "authorized": [],
        "clarification": None,
        "escalation": None,
        "retrieval_called": False,
        "retrieval_error": None,
    }

    original_retrieve = pipeline.retrieve_e5_steps
    original_select = pipeline.select_candidate_evidence
    original_authorize = pipeline.authorize_evidence
    original_clarify = pipeline.assess_clarification
    original_safety = pipeline.safety_response

    def capture_retrieval(*args, **kwargs):
        trace["retrieval_called"] = True

        try:
            records = original_retrieve(*args, **kwargs)
        except Exception as exc:
            trace["retrieval_error"] = type(exc).__name__
            raise

        trace["retrieved"] = [
            evidence_key(record)
            for record in records
        ]

        return records

    def capture_selection(*args, **kwargs):
        records = original_select(*args, **kwargs)

        trace["selected"] = [
            evidence_key(record)
            for record in records
        ]

        return records

    def capture_authorization(question, record, **kwargs):
        accepted = original_authorize(
            question,
            record,
            **kwargs,
        )

        if accepted:
            trace["authorized"].append(
                evidence_key(record)
            )

        return accepted

    def capture_clarification(*args, **kwargs):
        result = original_clarify(*args, **kwargs)
        trace["clarification"] = result
        return result

    def capture_safety(*args, **kwargs):
        result = original_safety(*args, **kwargs)
        trace["escalation"] = result
        return result

    started = time.perf_counter()

    with (
        patch.object(
            pipeline,
            "retrieve_e5_steps",
            side_effect=capture_retrieval,
        ),
        patch.object(
            pipeline,
            "select_candidate_evidence",
            side_effect=capture_selection,
        ),
        patch.object(
            pipeline,
            "authorize_evidence",
            side_effect=capture_authorization,
        ),
        patch.object(
            pipeline,
            "assess_clarification",
            side_effect=capture_clarification,
        ),
        patch.object(
            pipeline,
            "safety_response",
            side_effect=capture_safety,
        ),
    ):
        pipeline_trace = {}

        result = pipeline.answer_with_ann(
            row["question"],
            protocol_id=row.get("expected_protocol_id"),
            trace=pipeline_trace,
        )

    elapsed = time.perf_counter() - started

    expected = (
        row.get("expected_protocol_id"),
        row.get("expected_step_id"),
    )

    actual = [
        evidence_key(source)
        for source in result.get("sources", [])
    ]

    target_rank = None

    if expected in trace["retrieved"]:
        target_rank = (
            trace["retrieved"].index(expected) + 1
        )

    clarification = trace["clarification"]

    clarification_returned = bool(
        clarification
        and clarification.get("required")
        and result["answer"] == clarification.get("message")
    )

    escalation_returned = bool(
        trace["escalation"] is not None
        and result == trace["escalation"]
    )

    if actual:
        if (
            row["expected_action"] == "retrieve_step"
            and actual == [expected]
        ):
            outcome = "correct_evidence"
        else:
            outcome = "incorrect_evidence"

    elif (
        escalation_returned
        or (
            pipeline_trace.get("outcome") == "escalation"
            and result.get("needs_clinical_team") is True
            and not actual
        )
    ):
        outcome = "clinical_escalation"

    elif clarification_returned:
        outcome = "clarification"

    elif row.get("expected_protocol_id") is None:
        outcome = "missing_protocol_response"

    elif trace["retrieval_error"]:
        outcome = "retrieval_error"

    elif result["answer"] == SAFE_FALLBACK:
        outcome = "abstention"

    else:
        outcome = "other_response"

    if row["expected_action"] == "retrieve_step":

        if outcome == "correct_evidence":
            failure_stage = None

        elif outcome == "clinical_escalation":
            failure_stage = "safety_routing"

        elif outcome == "clarification":
            failure_stage = "clarification_routing"

        elif trace["retrieval_error"]:
            failure_stage = "retrieval_error"

        elif not trace["retrieval_called"]:
            failure_stage = "before_retrieval"

        elif target_rank is None:
            failure_stage = "neural_retrieval"

        elif expected not in trace["selected"]:
            failure_stage = "candidate_selection"

        elif expected not in trace["authorized"]:
            failure_stage = "authorization"

        else:
            failure_stage = "final_response"

    else:
        failure_stage = (
            None
            if outcome == "clarification"
            else "clarification_handling"
        )

    return {
        "id": row["id"],
        "language": row["language"],
        "expected_action": row["expected_action"],
        "expected_protocol_id": expected[0],
        "expected_step_id": expected[1],
        "target_rank": target_rank,
        "target_selected": expected in trace["selected"],
        "target_authorized": expected in trace["authorized"],
        "retrieval_called": trace["retrieval_called"],
        "retrieval_error": trace["retrieval_error"],
        "retrieved": trace["retrieved"],
        "selected": trace["selected"],
        "authorized": trace["authorized"],
        "returned_sources": actual,
        "outcome": outcome,
        "failure_stage": failure_stage,
        "latency_seconds": round(elapsed, 6),
    }


def summarize(rows):

    retrieval = [
        row for row in rows
        if row["expected_action"] == "retrieve_step"
    ]

    clarification = [
        row for row in rows
        if row["expected_action"] == "clarification_required"
    ]

    count = len(retrieval)

    def rate(value, total):
        return round(
            100 * value / total, 2
        ) if total else None

    correct = sum(
        row["outcome"] == "correct_evidence"
        for row in retrieval
    )

    incorrect = sum(
        row["outcome"] == "incorrect_evidence"
        for row in rows
    )

    answered = sum(
        bool(row["returned_sources"])
        for row in retrieval
    )

    retrieved = [
        row for row in retrieval
        if row["retrieval_called"]
    ]

    def recalled(k):
        return sum(
            row["target_rank"] is not None
            and row["target_rank"] <= k
            for row in retrieval
        )

    return {
        "total_questions": len(rows),
        "retrieval_questions": count,
        "clarification_questions": len(clarification),
        "retrieval_attempts": len(retrieved),

        "pipeline_recall_at_1": rate(recalled(1), count),
        "pipeline_recall_at_3": rate(recalled(3), count),
        "pipeline_recall_at_10": rate(recalled(10), count),

        "attempted_recall_at_1": rate(
            recalled(1), len(retrieved)
        ),
        "attempted_recall_at_3": rate(
            recalled(3), len(retrieved)
        ),
        "attempted_recall_at_10": rate(
            recalled(10), len(retrieved)
        ),

        "target_selection_rate": rate(
            sum(row["target_selected"] for row in retrieval),
            count,
        ),

        "target_authorization_rate": rate(
            sum(row["target_authorized"] for row in retrieval),
            count,
        ),

        "correct_evidence_answers": correct,
        "incorrect_evidence_answers": incorrect,
        "answer_coverage": rate(answered, count),
        "correct_evidence_rate": rate(correct, count),

        "accuracy_among_retrieval_answers": rate(
            correct, answered
        ),

        "clarification_matches": sum(
            row["outcome"] == "clarification"
            for row in clarification
        ),

        "outcomes": dict(
            Counter(row["outcome"] for row in rows)
        ),

        "failure_stages": dict(
            Counter(
                row["failure_stage"]
                for row in rows
                if row["failure_stage"] is not None
            )
        ),

        "median_latency_seconds": round(
            statistics.median(
                row["latency_seconds"]
                for row in rows
            ), 4
        ) if rows else None,
    }


def main():

    rows = json.loads(
        DATASET.read_text(encoding="utf-8-sig")
    )

    if len(rows) != 66:
        raise ValueError("Expected 66 development questions")

    print("ANN END-TO-END DEVELOPMENT EVALUATION", flush=True)
    print("Questions:", len(rows), flush=True)

    results = []

    for index, row in enumerate(rows, start=1):

        result = evaluate_question(row)
        results.append(result)

        print(
            f"[{index:02d}/{len(rows)}] "
            f"{result['id']} | "
            f"{result['language']} | "
            f"rank={result['target_rank']} | "
            f"{result['outcome']} | "
            f"stage={result['failure_stage']} | "
            f"{result['latency_seconds']:.3f}s",
            flush=True,
        )

    report = {
        "dataset": DATASET.name,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "overall": summarize(results),

        "by_language": {
            language: summarize([
                row for row in results
                if row["language"] == language
            ])
            for language in ("en", "hi", "hinglish")
        },

        "results": results,
    }

    attempts = [
        row for row in results
        if row["retrieval_called"]
    ]

    report["first_retrieval_latency_seconds"] = (
        attempts[0]["latency_seconds"]
        if attempts else None
    )

    report["subsequent_retrieval_median_seconds"] = (
        round(statistics.median(
            row["latency_seconds"]
            for row in attempts[1:]
        ), 4)
        if len(attempts) > 1 else None
    )

    RESULTS.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    output = RESULTS / (
        f"ann_pipeline_dev_{timestamp}.json"
    )

    with output.open("x", encoding="utf-8") as handle:
        json.dump(
            report,
            handle,
            indent=2,
            ensure_ascii=True,
        )

    print("\n--- OVERALL RESULTS ---")
    print(json.dumps(report["overall"], indent=2))

    print("\n--- LANGUAGE RESULTS ---")
    print(json.dumps(report["by_language"], indent=2))

    print(
        "\nFirst retrieval latency:",
        report["first_retrieval_latency_seconds"],
    )

    print(
        "Subsequent retrieval median:",
        report["subsequent_retrieval_median_seconds"],
    )

    print("\nReport saved:", output)
    print("EVALUATION COMPLETED")


if __name__ == "__main__":
    main()
