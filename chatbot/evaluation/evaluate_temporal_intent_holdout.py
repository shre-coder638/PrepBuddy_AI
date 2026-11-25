import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

from chatbot.ann.temporal_intent import detect_temporal_intent


BASE = Path(__file__).resolve().parent
RESULTS = BASE / "results"

QUESTIONS_FILE = BASE / "multilingual_temporal_holdout_questions.json"
LABELS_FILE = BASE / "multilingual_temporal_holdout_labels.json"
TUNING_FILE = BASE / "multilingual_temporal_questions.json"

REPORT_FILE = RESULTS / "multilingual_temporal_holdout_report.json"
CSV_FILE = RESULTS / "multilingual_temporal_holdout_summary.csv"

CLASSES = [None, "during_scan", "post_scan_discharge", "results_followup"]
LANGUAGES = ["en", "hi", "hinglish"]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_dataset(questions, labels, tuning_questions):
    if not isinstance(questions, list) or len(questions) != 60:
        raise ValueError("Expected exactly 60 holdout questions.")

    ids = [q.get("id") for q in questions]
    if None in ids or len(set(ids)) != 60:
        raise ValueError("Question IDs must be present and unique.")

    if not isinstance(labels, dict) or set(labels) != set(ids):
        raise ValueError("Question IDs and label IDs do not match exactly.")

    if any(label not in CLASSES for label in labels.values()):
        raise ValueError("Unsupported temporal intent label found.")

    language_counts = Counter()
    normalized_questions = set()

    tuning_ids = {q["id"] for q in tuning_questions}
    tuning_texts = {
        " ".join(q["question"].casefold().split())
        for q in tuning_questions
    }

    for q in questions:
        required = {
            "id", "language", "question", "expected_protocol_id",
            "expected_step_id", "expected_phase", "expected_action"
        }
        if not required.issubset(q):
            raise ValueError(f"Missing fields in question {q.get('id')}.")

        if q["language"] not in LANGUAGES:
            raise ValueError(f"Unsupported language in {q['id']}.")

        if not isinstance(q["question"], str) or not q["question"].strip():
            raise ValueError(f"Empty question in {q['id']}.")

        if q["expected_protocol_id"] != 14:
            raise ValueError(f"Unexpected protocol ID in {q['id']}.")

        if q["expected_action"] != "detect_temporal_intent":
            raise ValueError(f"Unexpected expected_action in {q['id']}.")

        normalized = " ".join(q["question"].casefold().split())

        if normalized in normalized_questions:
            raise ValueError(f"Duplicate holdout question: {q['id']}.")

        if normalized in tuning_texts:
            raise ValueError(f"Holdout question duplicates tuning data: {q['id']}.")

        normalized_questions.add(normalized)
        language_counts[q["language"]] += 1

    if language_counts != {"en": 20, "hi": 20, "hinglish": 20}:
        raise ValueError(f"Unexpected language distribution: {dict(language_counts)}")

    if tuning_ids.intersection(ids):
        raise ValueError("Holdout IDs overlap with tuning dataset IDs.")

    if len(tuning_questions) != 21:
        raise ValueError("Expected the original 21-question tuning dataset.")

    label_counts = Counter(labels.values())
    expected_counts = {
        None: 24,
        "during_scan": 12,
        "post_scan_discharge": 12,
        "results_followup": 12,
    }

    if label_counts != expected_counts:
        raise ValueError(f"Unexpected label distribution: {dict(label_counts)}")

    return language_counts, label_counts


def class_metrics(expected_values, predicted_values):
    rows = []

    for label in CLASSES:
        tp = sum(
            actual == label and predicted == label
            for actual, predicted in zip(expected_values, predicted_values)
        )
        fp = sum(
            actual != label and predicted == label
            for actual, predicted in zip(expected_values, predicted_values)
        )
        fn = sum(
            actual == label and predicted != label
            for actual, predicted in zip(expected_values, predicted_values)
        )
        support = sum(actual == label for actual in expected_values)
        predicted_count = sum(predicted == label for predicted in predicted_values)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        rows.append({
            "class": label,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "predicted_count": predicted_count,
        })

    return rows


def evaluate(questions, labels):
    expected_values = []
    predicted_values = []
    predictions = []

    for q in questions:
        expected = labels[q["id"]]
        predicted = detect_temporal_intent(q["question"])

        expected_values.append(expected)
        predicted_values.append(predicted)

        predictions.append({
            "id": q["id"],
            "language": q["language"],
            "question": q["question"],
            "expected": expected,
            "predicted": predicted,
            "correct": expected == predicted,
        })

    total = len(questions)
    correct = sum(p["correct"] for p in predictions)
    accuracy = correct / total

    per_class = class_metrics(expected_values, predicted_values)
    macro_f1 = sum(row["f1"] for row in per_class) / len(per_class)

    weighted_f1 = sum(
        row["f1"] * row["support"] for row in per_class
    ) / total

    confusion = {
        str(actual): {
            str(predicted): sum(
                a == actual and p == predicted
                for a, p in zip(expected_values, predicted_values)
            )
            for predicted in CLASSES
        }
        for actual in CLASSES
    }

    per_language = {}
    for language in LANGUAGES:
        language_rows = [p for p in predictions if p["language"] == language]
        language_correct = sum(p["correct"] for p in language_rows)

        per_language[language] = {
            "correct": language_correct,
            "total": len(language_rows),
            "accuracy": language_correct / len(language_rows),
        }

    return {
        "evaluation_name": "multilingual_temporal_holdout",
        "evaluation_scope": "diagnostic_only",
        "dataset_status": (
            "Independent from the original tuning questions, but previously "
            "used for diagnostic prediction inspection. Do not treat as an "
            "untouched final test set."
        ),
        "total_questions": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "class_metrics": per_class,
        "confusion_matrix": {
            "row_axis": "expected",
            "column_axis": "predicted",
            "class_order": [str(c) for c in CLASSES],
            "counts": confusion,
        },
        "per_language": per_language,
        "misclassifications": [
            p for p in predictions if not p["correct"]
        ],
        "limitations": [
            "Diagnostic evaluation only; not clinical validation.",
            "This dataset has already been inspected once against the detector.",
            "Do not tune the detector on these questions and call the result an untouched holdout score.",
            "Results apply only to the tested MRI temporal-intent examples and languages.",
        ],
    }, predictions


def write_csv(predictions):
    with CSV_FILE.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id", "language", "question",
                "expected", "predicted", "correct"
            ],
        )
        writer.writeheader()
        writer.writerows(predictions)


def main():
    for path in [QUESTIONS_FILE, LABELS_FILE, TUNING_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required dataset file not found: {path}")

    if REPORT_FILE.exists() or CSV_FILE.exists():
        raise FileExistsError(
            "Refusing to overwrite an existing holdout report or CSV."
        )

    questions = load_json(QUESTIONS_FILE)
    labels = load_json(LABELS_FILE)
    tuning_questions = load_json(TUNING_FILE)

    language_counts, label_counts = validate_dataset(
        questions, labels, tuning_questions
    )

    report, predictions = evaluate(questions, labels)

    RESULTS.mkdir(parents=True, exist_ok=True)

    # Recheck immediately before writing.
    if REPORT_FILE.exists() or CSV_FILE.exists():
        raise FileExistsError("An output file appeared; refusing to overwrite.")

    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(predictions)

    print("TEMPORAL INTENT HOLDOUT EVALUATION")
    print("=" * 42)
    print(f"Questions: {report['total_questions']}")
    print(f"Languages: {dict(language_counts)}")
    print(f"Gold labels: {dict(label_counts)}")
    print(f"Correct: {report['correct']}/{report['total_questions']}")
    print(f"Accuracy: {report['accuracy']:.2%}")
    print(f"Macro F1: {report['macro_f1']:.4f}")
    print(f"Weighted F1: {report['weighted_f1']:.4f}")

    print("\nPER-CLASS METRICS")
    for row in report["class_metrics"]:
        print(
            f"{str(row['class']):24} "
            f"P={row['precision']:.3f} "
            f"R={row['recall']:.3f} "
            f"F1={row['f1']:.3f} "
            f"support={row['support']}"
        )

    print("\nPER-LANGUAGE ACCURACY")
    for language, metrics in report["per_language"].items():
        print(
            f"{language}: {metrics['correct']}/{metrics['total']} "
            f"({metrics['accuracy']:.2%})"
        )

    print("\nCONFUSION MATRIX")
    print("Rows = expected; columns = predicted")
    print("Class order:", report["confusion_matrix"]["class_order"])
    for actual, row in report["confusion_matrix"]["counts"].items():
        print(actual, list(row.values()))

    print(f"\nMisclassifications: {len(report['misclassifications'])}")
    for item in report["misclassifications"]:
        print(
            f"{item['id']} [{item['language']}] "
            f"expected={item['expected']!r}, "
            f"predicted={item['predicted']!r}"
        )
        print(f"  {item['question']}")

    print("\nOUTPUT FILES")
    print(REPORT_FILE)
    print(CSV_FILE)
    print("\nScope: diagnostic only; not clinical validation.")


if __name__ == "__main__":
    main()
