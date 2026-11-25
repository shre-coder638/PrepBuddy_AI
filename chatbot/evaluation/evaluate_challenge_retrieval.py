"""Evaluate the separate 60-question multilingual challenge dataset."""

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

from chatbot.ann.retrieval import Retriever
from chatbot.evaluation.load_protocols import load_active_protocols


BASE_DIR = Path.cwd() / "chatbot" / "evaluation"

DATASET_PATH = BASE_DIR / "multilingual_challenge_questions.json"
RESULTS_DIR = BASE_DIR / "results"

MODEL_NAME = "intfloat/multilingual-e5-small"
TOP_K = 3


def load_questions() -> list[dict[str, object]]:
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        questions = json.load(file)

    if len(questions) != 60:
        raise ValueError(f"Expected 60 questions, found {len(questions)}")

    retrieval = [q for q in questions if q["expected_action"] == "retrieve_step"]
    clarification = [
        q for q in questions
        if q["expected_action"] == "clarification_required"
    ]

    if len(retrieval) != 54 or len(clarification) != 6:
        raise ValueError(
            f"Expected 54 retrieval and 6 clarification questions; "
            f"found {len(retrieval)} and {len(clarification)}"
        )

    return questions


def is_correct(record: dict[str, object], question: dict[str, object]) -> bool:
    return (
        record["protocol_id"] == question["expected_protocol_id"]
        and record["step_id"] == question["expected_step_id"]
    )


def calculate_metrics(results: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)

    for result in results:
        grouped[str(result["language"])].append(result)

    grouped["overall"] = results

    metrics = {}

    for language, items in grouped.items():
        if not items:
            continue

        metrics[language] = {
            "count": len(items),
            "recall_at_1": sum(
                item["target_rank"] == 1 for item in items
            ) / len(items),
            "recall_at_3": sum(
                item["target_rank"] is not None
                and item["target_rank"] <= TOP_K
                for item in items
            ) / len(items),
            "mrr": sum(
                1 / item["target_rank"]
                if item["target_rank"] is not None else 0
                for item in items
            ) / len(items),
        }

    return metrics


def calculate_target_metrics(
    results: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)

    for result in results:
        key = (
            int(result["expected_protocol_id"]),
            int(result["expected_step_id"]),
        )
        grouped[key].append(result)

    output = []

    for (protocol_id, step_id), items in sorted(grouped.items()):
        output.append({
            "protocol_id": protocol_id,
            "step_id": step_id,
            "count": len(items),
            "recall_at_1": sum(
                item["target_rank"] == 1 for item in items
            ) / len(items),
            "recall_at_3": sum(
                item["target_rank"] is not None
                and item["target_rank"] <= TOP_K
                for item in items
            ) / len(items),
            "mrr": sum(
                1 / item["target_rank"]
                if item["target_rank"] is not None else 0
                for item in items
            ) / len(items),
        })

    return output


def evaluate_baseline(
    records: list[dict[str, object]],
    questions: list[dict[str, object]],
) -> list[dict[str, object]]:
    retriever = Retriever(records)
    results = []

    for question in questions:
        ranked = retriever.search(
            str(question["question"]),
            limit=len(records),
        )

        target_rank = None
        candidates = []

        for rank, item in enumerate(ranked, start=1):
            record = item.record

            candidates.append({
                "rank": rank,
                "protocol_id": record["protocol_id"],
                "step_id": record["step_id"],
                "step": record["step"],
                "score": item.score,
            })

            if (
                question["expected_action"] == "retrieve_step"
                and is_correct(record, question)
            ):
                target_rank = rank

        results.append({
            "id": question["id"],
            "language": question["language"],
            "question": question["question"],
            "action": question["expected_action"],
            "expected_protocol_id": question["expected_protocol_id"],
            "expected_step_id": question["expected_step_id"],
            "target_rank": target_rank,
            "top_results": candidates[:TOP_K],
        })

    return results


def evaluate_e5(
    records: list[dict[str, object]],
    questions: list[dict[str, object]],
) -> list[dict[str, object]]:
    print(f"\nLoading E5 model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    passages = [
        "passage: " + str(record["text"])
        for record in records
    ]
    queries = [
        "query: " + str(question["question"])
        for question in questions
    ]

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

            if (
                question["expected_action"] == "retrieve_step"
                and is_correct(record, question)
            ):
                target_rank = rank

        results.append({
            "id": question["id"],
            "language": question["language"],
            "question": question["question"],
            "action": question["expected_action"],
            "expected_protocol_id": question["expected_protocol_id"],
            "expected_step_id": question["expected_step_id"],
            "target_rank": target_rank,
            "top_results": candidates[:TOP_K],
        })

    return results


def print_metrics(
    model_name: str,
    results: list[dict[str, object]],
) -> None:
    retrieval_results = [
        item for item in results if item["action"] == "retrieve_step"
    ]
    clarification_results = [
        item for item in results
        if item["action"] == "clarification_required"
    ]

    metrics = calculate_metrics(retrieval_results)

    print(f"\n{'=' * 65}")
    print(f"{model_name} — RETRIEVAL METRICS")
    print(f"{'=' * 65}")

    for language, values in metrics.items():
        print(
            f"{language:10} | "
            f"N={values['count']:2} | "
            f"R@1={values['recall_at_1']:.4f} | "
            f"R@3={values['recall_at_3']:.4f} | "
            f"MRR={values['mrr']:.4f}"
        )

    print("\nPER-TARGET RESULTS")

    for item in calculate_target_metrics(retrieval_results):
        print(
            f"Protocol {item['protocol_id']}, Step {item['step_id']} | "
            f"N={item['count']} | "
            f"R@1={item['recall_at_1']:.4f} | "
            f"R@3={item['recall_at_3']:.4f} | "
            f"MRR={item['mrr']:.4f}"
        )

    misses = [
        item for item in retrieval_results
        if item["target_rank"] is None or item["target_rank"] > TOP_K
    ]

    print(f"\nRETRIEVAL MISSES AT TOP {TOP_K}: {len(misses)}")

    for item in misses:
        print(
            f"{item['id']} ({item['language']}): "
            f"expected step {item['expected_step_id']}, "
            f"rank={item['target_rank']}"
        )

    print(
        f"\nCLARIFICATION QUESTIONS: {len(clarification_results)} "
        "(excluded from retrieval metrics)"
    )

    for item in clarification_results:
        print(f"\n{item['id']} ({item['language']}): {item['question']}")
        for candidate in item["top_results"]:
            print(
                f"  Rank {candidate['rank']}: "
                f"Protocol {candidate['protocol_id']}, "
                f"Step {candidate['step_id']} "
                f"({candidate['score']:.4f})"
            )


def main() -> None:
    print("Loading challenge dataset...")
    questions = load_questions()

    records = load_active_protocols()
    print(f"Protocol records loaded: {len(records)}")
    print(f"Challenge questions loaded: {len(questions)}")

    if len(records) != 58:
        raise ValueError(f"Expected 58 protocol records, found {len(records)}")

    retrieval_questions = [
        q for q in questions if q["expected_action"] == "retrieve_step"
    ]
    clarification_questions = [
        q for q in questions
        if q["expected_action"] == "clarification_required"
    ]

    print(f"Retrieval questions: {len(retrieval_questions)}")
    print(f"Clarification questions: {len(clarification_questions)}")

    print("\nRunning hashed baseline...")
    baseline_results = evaluate_baseline(records, questions)
    print_metrics("HASHED BASELINE", baseline_results)

    e5_results = evaluate_e5(records, questions)
    print_metrics("MULTILINGUAL E5", e5_results)

    baseline_retrieval = [
        item for item in baseline_results if item["action"] == "retrieve_step"
    ]
    e5_retrieval = [
        item for item in e5_results if item["action"] == "retrieve_step"
    ]

    baseline_clarification = [
        item for item in baseline_results
        if item["action"] == "clarification_required"
    ]
    e5_clarification = [
        item for item in e5_results
        if item["action"] == "clarification_required"
    ]

    report = {
        "dataset": DATASET_PATH.name,
        "protocol_record_count": len(records),
        "total_question_count": len(questions),
        "retrieval_question_count": len(retrieval_questions),
        "clarification_question_count": len(clarification_questions),
        "clarification_note": (
            "Clarification candidates are shown for manual inspection only. "
            "No automated clarification classifier or confidence threshold "
            "is evaluated."
        ),
        "models": {
            "hashed_baseline": {
                "metrics": calculate_metrics(baseline_retrieval),
                "target_metrics": calculate_target_metrics(baseline_retrieval),
                "retrieval_results": baseline_retrieval,
                "clarification_candidates": baseline_clarification,
            },
            "multilingual_e5": {
                "model_name": MODEL_NAME,
                "metrics": calculate_metrics(e5_retrieval),
                "target_metrics": calculate_target_metrics(e5_retrieval),
                "retrieval_results": e5_retrieval,
                "clarification_candidates": e5_clarification,
            },
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    report_path = RESULTS_DIR / "multilingual_challenge_retrieval_report.json"
    csv_path = RESULTS_DIR / "multilingual_challenge_retrieval_summary.csv"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    csv_rows = []

    for model_name, model_results in (
        ("hashed_baseline", baseline_results),
        ("multilingual_e5", e5_results),
    ):
        for item in model_results:
            csv_rows.append({
                "model": model_name,
                "id": item["id"],
                "language": item["language"],
                "action": item["action"],
                "expected_protocol_id": item["expected_protocol_id"],
                "expected_step_id": item["expected_step_id"],
                "target_rank": item["target_rank"],
                "top1_step_id": (
                    item["top_results"][0]["step_id"]
                    if item["top_results"] else ""
                ),
                "top2_step_id": (
                    item["top_results"][1]["step_id"]
                    if len(item["top_results"]) > 1 else ""
                ),
                "top3_step_id": (
                    item["top_results"][2]["step_id"]
                    if len(item["top_results"]) > 2 else ""
                ),
            })

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    print("\nEVALUATION COMPLETE")
    print(f"JSON report: {report_path}")
    print(f"CSV summary: {csv_path}")
    print(
        "Note: This is a technical retrieval benchmark, not clinical "
        "validation or approval."
    )


if __name__ == "__main__":
    main()
