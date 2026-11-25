import json

from chatbot.evaluation.load_protocols import load_active_protocols

base = "chatbot/evaluation/"

with open(base + "results/multilingual_dev_retrieval_report.json", encoding="utf-8") as f:
    report = json.load(f)

records = load_active_protocols()
record_map = {
    (r["protocol_id"], r["step_id"]): r
    for r in records
}

questions = {
    q["id"]: q
    for q in json.load(open(base + "multilingual_dev_questions.json", encoding="utf-8"))
}

misses = [
    r for r in report["retrieval_results"]
    if r["target_rank"] is None or r["target_rank"] > 3
]

for result in misses:
    question = questions[result["id"]]
    expected_key = (
        question["expected_protocol_id"],
        question["expected_step_id"],
    )
    expected = record_map[expected_key]

    print("\n" + "=" * 75)
    print("QUESTION:", result["id"], "|", result["language"])
    print("QUESTION TEXT:", question["question"].encode("unicode_escape").decode())
    print("EXPECTED STEP:", expected["step_id"], "|", expected["step"])
    print("EXPECTED INSTRUCTION:", expected["instruction"].encode("unicode_escape").decode())
    print("EXPECTED RANK:", result["target_rank"])

    print("\nTOP THREE RETRIEVED STEPS:")
    for candidate in result["top_results"]:
        record = record_map[(candidate["protocol_id"], candidate["step_id"])]
        print(
            f"\nRank {candidate['rank']} | "
            f"Protocol {candidate['protocol_id']} | "
            f"Step {candidate['step_id']} | "
            f"Score {candidate['score']:.4f}"
        )
        print("Title:", record["step"])
        print("Instruction:", record["instruction"].encode("unicode_escape").decode())
