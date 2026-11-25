"""Build question-evidence pairs for reviewed ANN relevance training."""

from __future__ import annotations

import os
import json
import hashlib

from pathlib import Path
from collections import Counter

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

import django
django.setup()

from chatbot.ann.protocol_records import load_protocol_records


ROOT = Path(__file__).resolve().parent

SOURCE = ROOT / "multilingual_dev_questions.json"

OUTPUT = (
    ROOT.parent
    / "datasets"
    / "relevance_review_v1.jsonl"
)


def make_pair_id(question_id, protocol_id, step_id):
    value = f"{question_id}:{protocol_id}:{step_id}"

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:24]


def main():

    if OUTPUT.exists():
        raise SystemExit(
            "Review dataset already exists. No changes made."
        )

    questions = json.loads(
        SOURCE.read_text(encoding="utf-8-sig")
    )

    questions = [
        row for row in questions
        if row["expected_action"] == "retrieve_step"
    ]

    if len(questions) != 60:
        raise ValueError(
            "Expected 60 development retrieval questions"
        )

    protocols = {}

    for protocol_id in (9, 11, 12, 13, 14):
        protocols[protocol_id] = load_protocol_records(
            protocol_id
        )

    pairs = []

    for question in questions:

        protocol_id = question["expected_protocol_id"]
        expected_step_id = question["expected_step_id"]

        records = protocols.get(protocol_id, [])

        if not records:
            raise ValueError(
                f"No records for protocol {protocol_id}"
            )

        expected_matches = [
            record for record in records
            if record["step_id"] == expected_step_id
        ]

        if len(expected_matches) != 1:
            raise ValueError(
                f"Invalid expected step: {question['id']}"
            )

        for record in records:

            expected_match = (
                record["step_id"] == expected_step_id
            )

            instruction_hash = hashlib.sha256(
                record["instruction"].encode("utf-8")
            ).hexdigest()

            pairs.append({
                "pair_id": make_pair_id(
                    question["id"],
                    protocol_id,
                    record["step_id"],
                ),
                "question_id": question["id"],
                "language": question["language"],
                "question": question["question"],
                "protocol_id": protocol_id,
                "protocol": record["protocol"],
                "step_id": record["step_id"],
                "step": record["step"],
                "instruction": record["instruction"],
                "instruction_sha256": instruction_hash,
                "is_critical": record["is_critical"],
                "expected_match": expected_match,

                # Retrieval labels are not clinical approval.
                "relevance_label": None,
                "requires_escalation": None,
                "review_status": "pending",
                "reviewer": None,
                "review_notes": None,
            })

    ids = [pair["pair_id"] for pair in pairs]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate pair IDs detected")

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT.open("x", encoding="utf-8") as handle:
        for pair in pairs:
            handle.write(
                json.dumps(
                    pair,
                    ensure_ascii=True,
                ) + "\n"
            )

    print("Source questions:", len(questions))
    print("Total question-evidence pairs:", len(pairs))

    print(
        "Existing retrieval-label matches:",
        sum(pair["expected_match"] for pair in pairs),
    )

    print(
        "Alternative instruction candidates:",
        sum(not pair["expected_match"] for pair in pairs),
    )

    print(
        "Language distribution:",
        dict(Counter(
            pair["language"] for pair in pairs
        )),
    )

    print(
        "Review status:",
        dict(Counter(
            pair["review_status"] for pair in pairs
        )),
    )

    print("Dataset saved:", OUTPUT)
    print("RELEVANCE REVIEW DATASET CREATED")


if __name__ == "__main__":
    main()
