import json
from pathlib import Path

path = Path("chatbot/evaluation/multilingual_dev_questions.json")

with path.open("r", encoding="utf-8") as f:
    questions = json.load(f)

replacements = {
    "DEVHI021": (
        "मुझे तैयारी के निर्देश याद नहीं हैं और मुझे यह भी याद नहीं है "
        "कि कौन-सी जाँच होने वाली है। मुझे क्या करना चाहिए?"
    ),
    "DEVHI022": (
        "क्या मुझे अंदर जाने से पहले इसे हटा देना चाहिए, "
        "या इसे लगा रहने देना सुरक्षित है?"
    ),
}

target_ids = set(replacements)

assert len(questions) == 66, "Unexpected dataset size"
assert sum(q["id"] in target_ids for q in questions) == 2, (
    "Expected exactly two target records"
)

# Snapshot all records that must remain unchanged.
before = [
    q.copy() for q in questions
    if q["id"] not in target_ids
]

for item in questions:
    if item["id"] in replacements:
        item["question"] = replacements[item["id"]]

# Verify both replacements contain Devanagari.
for item in questions:
    if item["id"] in target_ids:
        assert any("\u0900" <= ch <= "\u097F" for ch in item["question"]), (
            f"Devanagari missing in {item['id']}"
        )

# Verify the other 64 records are unchanged.
after = [
    q.copy() for q in questions
    if q["id"] not in target_ids
]
assert before == after, "An unrelated record was modified"

# Save without a UTF-8 BOM.
path.write_text(
    json.dumps(questions, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

# Reopen and verify persisted content.
with path.open("r", encoding="utf-8") as f:
    saved = json.load(f)

saved_map = {q["id"]: q for q in saved}

for question_id, expected_text in replacements.items():
    assert saved_map[question_id]["question"] == expected_text

assert len(saved) == 66

print("Hindi clarification repair successful.")
print("Repaired records: 2")
print("Other records preserved:", len(before))
print("Total records:", len(saved))
print("UTF-8 persistence: PASSED")

for question_id in sorted(target_ids):
    text = saved_map[question_id]["question"]
    print(f"\n{question_id}:")
    print(text.encode("unicode_escape").decode())
