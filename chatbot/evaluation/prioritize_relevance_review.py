"""Prioritize question-evidence pairs for human review."""

from __future__ import annotations

import json
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parent

DATASET = (
    ROOT.parent
    / "datasets"
    / "relevance_review_v1.jsonl"
)

REPORT = (
    ROOT
    / "results"
    / "ann_pipeline_dev_20261125T103053794887Z.json"
)

OUTPUT = (
    ROOT.parent
    / "datasets"
    / "relevance_review_priority_v1.jsonl"
)


def main():

    if OUTPUT.exists():
        raise SystemExit(
            "Priority dataset already exists. "
            "No changes made."
        )

    pairs = [
        json.loads(line)
        for line in DATASET.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    report = json.loads(
        REPORT.read_text(encoding="utf-8")
    )

    diagnostics = {
        row["id"]: row
        for row in report["results"]
    }

    prioritized = []

    for pair in pairs:

        question_id = pair["question_id"]

        if question_id not in diagnostics:
            raise ValueError(
                f"Missing diagnostics: {question_id}"
            )

        trace = diagnostics[question_id]

        key = (
            pair["protocol_id"],
            pair["step_id"],
        )

        retrieved = [
            tuple(item)
            for item in trace["retrieved"]
        ]

        selected = {
            tuple(item)
            for item in trace["selected"]
        }

        rank = (
            retrieved.index(key) + 1
            if key in retrieved
            else None
        )

        reasons = []

        if pair["expected_match"]:
            reasons.append("expected_retrieval_match")

        if rank is not None and rank <= 3:
            reasons.append("top_three_retrieval")

        if key in selected:
            reasons.append("existing_candidate_match")

        if not reasons:
            continue

        if pair["expected_match"]:
            priority = 1
        elif key in selected:
            priority = 2
        else:
            priority = 3

        prioritized.append({
            **pair,
            "review_priority": priority,
            "review_reasons": reasons,
            "baseline_retrieval_rank": rank,
            "baseline_failure_stage": trace[
                "failure_stage"
            ],
        })

    prioritized.sort(
        key=lambda pair: (
            pair["review_priority"],
            pair["question_id"],
            pair["baseline_retrieval_rank"] or 999,
            pair["step_id"],
        )
    )

    assert sum(
        pair["expected_match"]
        for pair in prioritized
    ) == 60

    assert len({
        pair["pair_id"]
        for pair in prioritized
    }) == len(prioritized)

    assert all(
        pair["review_status"] == "pending"
        for pair in prioritized
    )

    with OUTPUT.open("x", encoding="utf-8") as handle:
        for pair in prioritized:
            handle.write(
                json.dumps(
                    pair,
                    ensure_ascii=True,
                ) + "\n"
            )

    print("Original dataset pairs:", len(pairs))
    print("Prioritized pairs:", len(prioritized))

    print(
        "Expected matches:",
        sum(
            pair["expected_match"]
            for pair in prioritized
        ),
    )

    print(
        "Alternative candidates:",
        sum(
            not pair["expected_match"]
            for pair in prioritized
        ),
    )

    print(
        "Priority distribution:",
        dict(Counter(
            pair["review_priority"]
            for pair in prioritized
        )),
    )

    print(
        "Language distribution:",
        dict(Counter(
            pair["language"]
            for pair in prioritized
        )),
    )

    print(
        "Review status:",
        dict(Counter(
            pair["review_status"]
            for pair in prioritized
        )),
    )

    print("Dataset saved:", OUTPUT)
    print("PRIORITIZED REVIEW DATASET CREATED")


if __name__ == "__main__":
    main()
