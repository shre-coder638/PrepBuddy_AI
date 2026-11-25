"""Prepare provisional relevance training data with leakage controls."""

from __future__ import annotations

import csv
import json
import hashlib

from pathlib import Path
from collections import Counter, defaultdict


ROOT = Path(__file__).resolve().parent.parent

DATASETS = ROOT / "datasets"

ANNOTATED = (
    DATASETS / "relevance_review_provisional_v1.csv"
)

ORIGINAL = (
    DATASETS / "relevance_review_priority_v1.jsonl"
)

OUTPUT = (
    DATASETS / "relevance_training_experimental_v1.jsonl"
)

DEV_QUESTIONS = (
    ROOT
    / "evaluation"
    / "multilingual_dev_questions.json"
)

LABELS = {
    "direct_support": 1,
    "partial_support": 0,
    "irrelevant": 0,
    "conflicting": 0,
}


def main():

    if OUTPUT.exists():
        raise SystemExit(
            "Training dataset already exists. "
            "No changes made."
        )

    with ANNOTATED.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        annotations = list(csv.DictReader(handle))

    original_rows = [
        json.loads(line)
        for line in ORIGINAL.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    originals = {
        row["pair_id"]: row
        for row in original_rows
    }

    questions = {
        row["id"]: row
        for row in json.loads(
            DEV_QUESTIONS.read_text(
                encoding="utf-8-sig"
            )
        )
    }

    if not (
        len(annotations)
        == len(original_rows)
        == len(originals)
        == 153
    ):
        raise ValueError("Unexpected dataset size")

    annotated_ids = [
        row["pair_id"]
        for row in annotations
    ]

    if len(set(annotated_ids)) != len(annotated_ids):
        raise ValueError("Duplicate annotation IDs")

    if set(annotated_ids) != set(originals):
        raise ValueError("Annotation ID mismatch")

    training_rows = []

    for annotation in annotations:

        source = originals[annotation["pair_id"]]

        for field in (
            "question_id",
            "language",
            "question",
            "protocol",
            "step",
            "instruction",
        ):
            if annotation[field] != source[field]:
                raise ValueError(
                    f"Modified source field: {field}"
                )

        if annotation["review_status"] != "provisional":
            raise ValueError("Unexpected review status")

        label = annotation["relevance_label"]

        if label not in LABELS:
            raise ValueError(
                f"Invalid relevance label: {label}"
            )

        escalation = annotation[
            "requires_escalation"
        ].strip().lower()

        if escalation not in {"true", "false"}:
            raise ValueError(
                "Invalid escalation label"
            )

        instruction_hash = hashlib.sha256(
            source["instruction"].encode("utf-8")
        ).hexdigest()

        if (
            instruction_hash
            != source["instruction_sha256"]
        ):
            raise ValueError(
                "Instruction integrity check failed"
            )

        question = questions[
            source["question_id"]
        ]

        if question["expected_action"] != "retrieve_step":
            raise ValueError(
                "Unexpected source question type"
            )

        if (
            question["question"] != source["question"]
            or question["language"] != source["language"]
            or question["expected_protocol_id"]
            != source["protocol_id"]
        ):
            raise ValueError(
                "Source question mismatch"
            )

        # Group by the question's expected instruction,
        # not by the candidate instruction.
        family_id = (
            f"p{question['expected_protocol_id']}"
            f"_s{question['expected_step_id']}"
        )

        training_rows.append({
            "pair_id": source["pair_id"],
            "question_id": source["question_id"],
            "question_family_id": family_id,
            "language": source["language"],
            "question": source["question"],
            "protocol_id": source["protocol_id"],
            "protocol": source["protocol"],
            "step_id": source["step_id"],
            "step": source["step"],
            "instruction": source["instruction"],
            "instruction_sha256": instruction_hash,
            "relevance_label": label,
            "target": LABELS[label],
            "requires_escalation": escalation == "true",
            "review_status": "provisional",
            "reviewer": annotation["reviewer"],
            "review_notes": annotation["review_notes"],
            "experimental_only": True,
            "clinical_approval": False,
        })

    groups = defaultdict(list)

    for row in training_rows:
        groups[
            row["question_family_id"]
        ].append(row)

    question_groups = defaultdict(set)

    for row in training_rows:
        question_groups[row["question_id"]].add(
            row["question_family_id"]
        )

    assert all(
        len(group_ids) == 1
        for group_ids in question_groups.values()
    )

    assert Counter(
        row["target"]
        for row in training_rows
    ) == {0: 98, 1: 55}

    with OUTPUT.open("x", encoding="utf-8") as handle:
        for row in training_rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=True,
                ) + "\n"
            )

    print("Training pairs:", len(training_rows))

    print(
        "Unique questions:",
        len(question_groups),
    )

    print(
        "Question families:",
        len(groups),
    )

    print(
        "Binary targets:",
        dict(Counter(
            row["target"]
            for row in training_rows
        )),
    )

    print("\n--- Question family distribution ---")

    for family_id, rows in sorted(groups.items()):

        print(
            f"{family_id} | "
            f"Pairs={len(rows)} | "
            f"Questions={len({r['question_id'] for r in rows})} | "
            f"Positive={sum(r['target'] for r in rows)} | "
            f"Negative={sum(1-r['target'] for r in rows)}"
        )

    print("\nQuestion grouping verification: PASS")
    print("Instruction hash verification: PASS")
    print("Clinical approval status: NOT APPROVED")
    print("Training mode: EXPERIMENTAL ONLY")
    print("Dataset saved:", OUTPUT)
    print("TRAINING DATA PREPARATION COMPLETED")


if __name__ == "__main__":
    main()
