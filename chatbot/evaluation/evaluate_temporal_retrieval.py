"""Evaluate baseline multilingual E5 retrieval on the MRI temporal dataset."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import numpy as np
from sentence_transformers import SentenceTransformer

from chatbot.evaluation.load_protocols import load_active_protocols


BASE_DIR = Path.cwd() / "chatbot" / "evaluation"
DATASET_PATH = BASE_DIR / "multilingual_temporal_questions.json"
RESULTS_DIR = BASE_DIR / "results"

MODEL_NAME = "intfloat/multilingual-e5-small"
TOP_K = 3
EXPECTED_STEPS = {74, 75, 79, 80, 82, 84, 85}


def load_questions():
    with DATASET_PATH.open("r", encoding="utf-8-sig") as file:
        questions = json.load(file)

    if len(questions) != 21:
        raise ValueError(f"Expected 21 questions, found {len(questions)}")

    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate question IDs found")

    expected_languages = {"en": 7, "hi": 7, "hinglish": 7}
    actual_languages = defaultdict(int)

    for q in questions:
        actual_languages[q["language"]] += 1

        if q["expected_protocol_id"] != 14:
            raise ValueError(f"{q['id']}: unexpected protocol")

        if q["expected_step_id"] not in EXPECTED_STEPS:
            raise ValueError(f"{q['id']}: unexpected expected step")

        if q["expected_action"] != "retrieve_step":
            raise ValueError(f"{q['id']}: unexpected action")

        if q["expected_phase"] not in {"before", "during", "after"}:
            raise ValueError(f"{q['id']}: invalid phase")

    if dict(actual_languages) != expected_languages:
        raise ValueError(f"Unexpected language distribution: {dict(actual_languages)}")

    return questions


def is_correct(record, question):
    return (
        record["protocol_id"] == question["expected_protocol_id"]
        and record["step_id"] == question["expected_step_id"]
    )


def evaluate_e5(records, questions):
    print(f"\nLoading E5 model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    passages = ["passage: " + str(r["text"]) for r in records]
    queries = ["query: " + str(q["question"]) for q in questions]

    passage_vectors = model.encode(
        passages,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    query_vectors = model.encode(
        queries,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    similarities = np.matmul(query_vectors, passage_vectors.T)
    results = []

    for question, scores in zip(questions, similarities):
        ranked_indices = np.argsort(scores)[::-1]
        target_rank = None
        candidates = []

        for rank, index in enumerate(ranked_indices, start=1):
            record = records[int(index)]

            candidates.append({
                "rank": rank,
                "protocol_id": record["protocol_id"],
                "step_id": record["step_id"],
                "step": record["step"],
                "score": float(scores[index]),
            })

            if is_correct(record, question):
                target_rank = rank

        results.append({
            "id": question["id"],
            "language": question["language"],
            "phase": question["expected_phase"],
            "question": question["question"],
            "expected_protocol_id": question["expected_protocol_id"],
            "expected_step_id": question["expected_step_id"],
            "target_rank": target_rank,
            "top_results": candidates[:TOP_K],
            "all_results": candidates,
        })

    return results


def calculate_metrics(results):
    if not results:
        return {"count": 0, "recall_at_1": 0, "recall_at_3": 0, "mrr": 0}

    return {
        "count": len(results),
        "recall_at_1": sum(
            r["target_rank"] == 1 for r in results
        ) / len(results),
        "recall_at_3": sum(
            r["target_rank"] is not None and r["target_rank"] <= TOP_K
            for r in results
        ) / len(results),
        "mrr": sum(
            1 / r["target_rank"] if r["target_rank"] is not None else 0
            for r in results
        ) / len(results),
    }


def grouped_metrics(results, field):
    groups = defaultdict(list)

    for result in results:
        groups[result[field]].append(result)

    return {
        key: calculate_metrics(items)
        for key, items in sorted(groups.items())
    }


def print_metrics(title, metrics):
    print("\n" + title)
    print("-" * 75)

    for name, values in metrics.items():
        print(
            f"{name:12} | N={values['count']:2} | "
            f"R@1={values['recall_at_1']:.4f} | "
            f"R@3={values['recall_at_3']:.4f} | "
            f"MRR={values['mrr']:.4f}"
        )


def main():
    print("Loading temporal diagnostic dataset...")
    questions = load_questions()

    records = [
        r for r in load_active_protocols()
        if r["protocol_id"] == 14
    ]

    if len(records) != 13:
        raise ValueError(f"Expected 13 MRI records, found {len(records)}")

    available_steps = {r["step_id"] for r in records}
    if not EXPECTED_STEPS.issubset(available_steps):
        raise ValueError("One or more expected MRI steps are missing")

    print("MRI protocol records:", len(records))
    print("Temporal questions:", len(questions))

    results = evaluate_e5(records, questions)

    overall = {"overall": calculate_metrics(results)}
    languages = grouped_metrics(results, "language")
    phases = grouped_metrics(results, "phase")
    targets = grouped_metrics(results, "expected_step_id")

    print_metrics("OVERALL BASELINE", overall)
    print_metrics("BASELINE BY LANGUAGE", languages)
    print_metrics("BASELINE BY TEMPORAL PHASE", phases)
    print_metrics("BASELINE BY EXPECTED STEP", targets)

    misses = [
        r for r in results
        if r["target_rank"] is None or r["target_rank"] > TOP_K
    ]

    print(f"\nMISSES OUTSIDE TOP {TOP_K}: {len(misses)}")

    for item in misses:
        print(
            f"\n{item['id']} ({item['language']}, {item['phase']}): "
            f"expected step {item['expected_step_id']}, "
            f"rank={item['target_rank']}"
        )

        for candidate in item["top_results"]:
            print(
                f"  Rank {candidate['rank']}: "
                f"Step {candidate['step_id']} "
                f"({candidate['score']:.4f})"
            )

    report = {
        "dataset": DATASET_PATH.name,
        "model_name": MODEL_NAME,
        "protocol_id": 14,
        "protocol_record_count": len(records),
        "question_count": len(questions),
        "overall_metrics": overall,
        "language_metrics": languages,
        "phase_metrics": phases,
        "target_metrics": targets,
        "results": results,
        "evaluation_note": (
            "Baseline technical retrieval evaluation only. "
            "Not clinical validation or approval."
        ),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    report_path = RESULTS_DIR / "multilingual_temporal_baseline_report.json"
    csv_path = RESULTS_DIR / "multilingual_temporal_baseline_summary.csv"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id", "language", "phase", "expected_step_id",
                "target_rank", "top1_step_id", "top2_step_id",
                "top3_step_id",
            ],
        )
        writer.writeheader()

        for item in results:
            top = item["top_results"]
            writer.writerow({
                "id": item["id"],
                "language": item["language"],
                "phase": item["phase"],
                "expected_step_id": item["expected_step_id"],
                "target_rank": item["target_rank"],
                "top1_step_id": top[0]["step_id"] if len(top) > 0 else "",
                "top2_step_id": top[1]["step_id"] if len(top) > 1 else "",
                "top3_step_id": top[2]["step_id"] if len(top) > 2 else "",
            })

    print("\nBASELINE EVALUATION COMPLETE")
    print("JSON report:", report_path)
    print("CSV summary:", csv_path)


if __name__ == "__main__":
    main()
