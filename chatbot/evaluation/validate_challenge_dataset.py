"""Structural validator for the 60-question multilingual challenge dataset."""

import json
from collections import Counter
from pathlib import Path

DATASET = Path(__file__).with_name("multilingual_challenge_questions.json")

EXPECTED_LANGUAGES = {"en", "hi", "hinglish"}
EXPECTED_TARGETS = {
    (11, 39), (11, 45),
    (12, 55), (12, 57),
    (9, 20), (9, 22),
    (13, 63), (13, 67),
    (14, 75), (14, 79),
}

EXPECTED_FIELDS = {
    "id",
    "language",
    "question",
    "expected_protocol_id",
    "expected_step_id",
    "expected_action",
}

def main():
    if not DATASET.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET}")

    with DATASET.open(encoding="utf-8-sig") as file:
        questions = json.load(file)

    errors = []

    if not isinstance(questions, list):
        raise ValueError("Dataset must contain a JSON list.")

    if len(questions) != 60:
        errors.append(f"Expected 60 questions; found {len(questions)}.")

    ids = []
    language_counts = Counter()
    action_counts = Counter()
    target_counts = Counter()

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            errors.append(f"Record {index} is not a JSON object.")
            continue

        missing = EXPECTED_FIELDS - question.keys()
        extra = question.keys() - EXPECTED_FIELDS

        if missing:
            errors.append(f"Record {index}: missing fields {sorted(missing)}.")
        if extra:
            errors.append(f"Record {index}: unexpected fields {sorted(extra)}.")

        qid = question.get("id")
        language = question.get("language")
        action = question.get("expected_action")

        if not isinstance(qid, str) or not qid.strip():
            errors.append(f"Record {index}: invalid ID.")
        else:
            ids.append(qid)

        if language not in EXPECTED_LANGUAGES:
            errors.append(f"{qid}: invalid language {language!r}.")
        else:
            language_counts[language] += 1

        if not isinstance(question.get("question"), str) or not question["question"].strip():
            errors.append(f"{qid}: empty or invalid question.")

        if action not in {"retrieve_step", "clarification_required"}:
            errors.append(f"{qid}: invalid action {action!r}.")
            continue

        action_counts[action] += 1

        protocol_id = question.get("expected_protocol_id")
        step_id = question.get("expected_step_id")

        if action == "retrieve_step":
            target = (protocol_id, step_id)
            if target not in EXPECTED_TARGETS:
                errors.append(f"{qid}: invalid retrieval target {target}.")
            else:
                target_counts[target] += 1

        elif protocol_id is not None or step_id is not None:
            errors.append(
                f"{qid}: clarification question must have null protocol and step IDs."
            )

    duplicates = [
        qid for qid, count in Counter(ids).items()
        if count > 1
    ]
    if duplicates:
        errors.append(f"Duplicate IDs: {duplicates}")

    if language_counts != {"en": 20, "hi": 20, "hinglish": 20}:
        errors.append(f"Incorrect language distribution: {dict(language_counts)}.")

    if action_counts != {
        "retrieve_step": 54,
        "clarification_required": 6,
    }:
        errors.append(f"Incorrect action distribution: {dict(action_counts)}.")

    for language in EXPECTED_LANGUAGES:
        records = [q for q in questions if isinstance(q, dict) and q.get("language") == language]
        language_actions = Counter(q.get("expected_action") for q in records)

        if language_actions != {
            "retrieve_step": 18,
            "clarification_required": 2,
        }:
            errors.append(
                f"{language}: expected 18 retrieval and 2 clarification questions; "
                f"found {dict(language_actions)}."
            )

    print("Dataset:", DATASET)
    print("Total questions:", len(questions))
    print("Unique IDs:", len(set(ids)))
    print("Languages:", dict(language_counts))
    print("Actions:", dict(action_counts))
    print("Retrieval targets:")
    for target, count in sorted(target_counts.items()):
        print(f"  Protocol {target[0]}, Step {target[1]}: {count}")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print("-", error)
        raise SystemExit(1)

    print("\nVALIDATION PASSED")
    print("All structural checks passed. This does not establish clinical approval.")

if __name__ == "__main__":
    main()
