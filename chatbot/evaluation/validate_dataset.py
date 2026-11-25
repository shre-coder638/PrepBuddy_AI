import json
from collections import Counter
from pathlib import Path

from chatbot.evaluation.load_protocols import load_active_protocols

dataset_path = Path("chatbot/evaluation/multilingual_questions.json")

with dataset_path.open(encoding="utf-8-sig") as file:
    questions = json.load(file)

records = load_active_protocols()

valid_targets = {
    (record["protocol_id"], record["step_id"])
    for record in records
}

ids = [question["id"] for question in questions]
language_counts = Counter(
    question["language"] for question in questions
)

invalid_targets = [
    question for question in questions
    if (
        question["expected_protocol_id"],
        question["expected_step_id"],
    ) not in valid_targets
]

empty_questions = [
    question["id"] for question in questions
    if not question["question"].strip()
]

print("Total questions:", len(questions))
print("Language distribution:", dict(language_counts))
print("Unique question IDs:", len(set(ids)))
print("Invalid targets:", invalid_targets)
print("Empty questions:", empty_questions)

assert len(questions) == 30, "Expected exactly 30 questions"
assert len(set(ids)) == 30, "Duplicate question IDs found"
assert language_counts == {
    "en": 10,
    "hi": 10,
    "hinglish": 10,
}, "Unexpected language distribution"
assert not invalid_targets, "Invalid protocol/step labels"
assert not empty_questions, "Empty questions found"

print("DATASET VALIDATION PASSED")
