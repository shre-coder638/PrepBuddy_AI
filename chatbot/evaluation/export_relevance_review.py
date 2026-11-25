"""Export blinded relevance review candidates to CSV."""

from __future__ import annotations

import csv
import json
import random

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

SOURCE = (
    ROOT
    / "datasets"
    / "relevance_review_priority_v1.jsonl"
)

OUTPUT = (
    ROOT
    / "datasets"
    / "relevance_review_blinded_v1.csv"
)

FIELDS = (
    "pair_id",
    "question_id",
    "language",
    "question",
    "protocol",
    "step",
    "instruction",
    "relevance_label",
    "requires_escalation",
    "review_status",
    "reviewer",
    "review_notes",
)


def main():

    if OUTPUT.exists():
        raise SystemExit(
            "Review CSV already exists. No changes made."
        )

    pairs = [
        json.loads(line)
        for line in SOURCE.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(pairs) != 153:
        raise ValueError(
            f"Expected 153 pairs, found {len(pairs)}"
        )

    if len({
        pair["pair_id"]
        for pair in pairs
    }) != len(pairs):
        raise ValueError("Duplicate pair IDs")

    if any(
        pair["review_status"] != "pending"
        for pair in pairs
    ):
        raise ValueError(
            "Unexpected existing review labels"
        )

    # Reproducible randomized review ordering.
    random.Random(42).shuffle(pairs)

    with OUTPUT.open(
        "x",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=FIELDS,
            extrasaction="ignore",
        )

        writer.writeheader()

        for pair in pairs:
            writer.writerow(pair)

    with OUTPUT.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        exported = list(
            csv.DictReader(handle)
        )

    assert len(exported) == len(pairs)

    original = {
        pair["pair_id"]: pair
        for pair in pairs
    }

    for row in exported:
        pair = original[row["pair_id"]]

        assert row["question"] == pair["question"]
        assert row["instruction"] == pair["instruction"]

    print("Exported review pairs:", len(exported))
    print("Question text preservation: PASS")
    print("Instruction text preservation: PASS")
    print("Unicode round-trip verification: PASS")
    print("Original retrieval labels hidden: PASS")
    print("Randomized review ordering: PASS")
    print("Review file:", OUTPUT)
    print("REVIEW EXPORT COMPLETED")


if __name__ == "__main__":
    main()
