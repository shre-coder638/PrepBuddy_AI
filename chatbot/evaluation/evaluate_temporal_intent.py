import csv
import json
from pathlib import Path

from chatbot.ann.temporal_intent import detect_temporal_intent

BASE = Path(__file__).resolve().parent
QUESTIONS = BASE / "multilingual_temporal_questions.json"
LABELS = BASE / "multilingual_temporal_intent_labels.json"
RESULTS = BASE / "results"

REPORT = RESULTS / "multilingual_temporal_intent_candidate1_report.json"
CSV_FILE = RESULTS / "multilingual_temporal_intent_candidate1_summary.csv"

CLASSES = [None, "during_scan", "post_scan_discharge", "results_followup"]
NAMES = {None: "none", **{name: name for name in CLASSES if name is not None}}


def metrics(rows):
    total = len(rows)
    correct = sum(r["expected"] == r["predicted"] for r in rows)
    per_class = {}

    for label in CLASSES:
        tp = sum(r["expected"] == label and r["predicted"] == label for r in rows)
        actual = sum(r["expected"] == label for r in rows)
        predicted = sum(r["predicted"] == label for r in rows)

        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

        per_class[NAMES[label]] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": actual,
            "predicted_count": predicted,
        }

    confusion = {
        NAMES[actual]: {
            NAMES[predicted]: sum(
                r["expected"] == actual and r["predicted"] == predicted
                for r in rows
            )
            for predicted in CLASSES
        }
        for actual in CLASSES
    }

    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(CLASSES)
    weighted_f1 = (
        sum(v["f1"] * v["support"] for v in per_class.values()) / total
        if total else 0.0
    )

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def main():
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8-sig"))
    labels = json.loads(LABELS.read_text(encoding="utf-8-sig"))

    ids = [item.get("id") for item in questions]
    if len(questions) != 21 or len(set(ids)) != 21:
        raise ValueError("Expected 21 questions with unique IDs.")
    if set(ids) != set(labels):
        raise ValueError("Question IDs and gold-label IDs do not match.")
    if any(value not in CLASSES for value in labels.values()):
        raise ValueError("Unsupported gold label.")
    if {item.get("language") for item in questions} != {"en", "hi", "hinglish"}:
        raise ValueError("Unexpected language distribution.")

    rows = []
    for item in questions:
        expected = labels[item["id"]]
        predicted = detect_temporal_intent(item["question"])
        rows.append({
            "id": item["id"],
            "language": item["language"],
            "expected": expected,
            "predicted": predicted,
            "correct": expected == predicted,
            "question": item["question"],
        })

    overall = metrics(rows)
    by_language = {
        language: metrics([r for r in rows if r["language"] == language])
        for language in ("en", "hi", "hinglish")
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    if REPORT.exists() or CSV_FILE.exists():
        raise FileExistsError("Refusing to overwrite an existing report.")

    report = {
        "evaluation": "multilingual_temporal_intent_baseline",
        "scope": "Diagnostic evaluation only; not clinical validation.",
        "total_questions": len(rows),
        "gold_label_distribution": {
            NAMES[label]: sum(r["expected"] == label for r in rows)
            for label in CLASSES
        },
        "overall": overall,
        "by_language": by_language,
        "limitations": [
            "Only 21 MRI-related questions are evaluated.",
            "Each temporal intent has only three positive examples.",
            "Results do not establish clinical safety or production readiness.",
        ],
    }

    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with CSV_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "id", "language", "expected_intent",
            "predicted_intent", "correct", "question",
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "id": r["id"],
                "language": r["language"],
                "expected_intent": NAMES[r["expected"]],
                "predicted_intent": NAMES[r["predicted"]],
                "correct": r["correct"],
                "question": r["question"],
            })

    print("TEMPORAL INTENT EVALUATION")
    print("=" * 45)
    print(f"Questions: {overall['total']}")
    print(f"Correct: {overall['correct']}")
    print(f"Accuracy: {overall['accuracy']:.2%}")
    print(f"Macro F1: {overall['macro_f1']:.4f}")
    print(f"Weighted F1: {overall['weighted_f1']:.4f}")

    print("\nPer-class metrics:")
    for name, result in overall["per_class"].items():
        print(
            f"{name:24s} P={result['precision']:.3f} "
            f"R={result['recall']:.3f} F1={result['f1']:.3f} "
            f"support={result['support']}"
        )

    names = [NAMES[label] for label in CLASSES]
    print("\nConfusion matrix (rows=expected, columns=predicted):")
    print("expected/predicted | " + " | ".join(names))
    for actual in names:
        values = [str(overall["confusion_matrix"][actual][pred]) for pred in names]
        print(f"{actual:24s} | " + " | ".join(values))

    print("\nPer-language accuracy:")
    for language, result in by_language.items():
        print(f"{language}: {result['correct']}/{result['total']} ({result['accuracy']:.2%})")

    print("\nReports created:")
    print(REPORT)
    print(CSV_FILE)


if __name__ == "__main__":
    main()
