import csv
import json
import os
from collections import defaultdict
from pathlib import Path

# Force offline loading: the multilingual model was already downloaded.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import numpy as np
from sentence_transformers import SentenceTransformer

from chatbot.ann.retrieval import Retriever
from chatbot.evaluation.load_protocols import load_active_protocols


BASE_DIR = Path("chatbot/evaluation")
RESULTS_DIR = BASE_DIR / "results"
DATASET_PATH = BASE_DIR / "multilingual_questions.json"
MODEL_NAME = "intfloat/multilingual-e5-small"

TOP_K = 3


def load_questions():
    with DATASET_PATH.open(encoding="utf-8-sig") as file:
        return json.load(file)


def is_correct(record, question):
    return (
        record["protocol_id"] == question["expected_protocol_id"]
        and record["step_id"] == question["expected_step_id"]
    )


def calculate_metrics(results):
    grouped = defaultdict(list)

    for result in results:
        grouped[result["language"]].append(result)

    grouped["overall"] = results

    metrics = {}

    for language, items in grouped.items():
        count = len(items)
        metrics[language] = {
            "questions": count,
            "recall_at_1": round(
                sum(item["target_rank"] == 1 for item in items) / count, 4
            ),
            "recall_at_3": round(
                sum(
                    item["target_rank"] is not None
                    and item["target_rank"] <= 3
                    for item in items
                ) / count, 4
            ),
            "mean_reciprocal_rank": round(
                sum(
                    1 / item["target_rank"]
                    if item["target_rank"] is not None else 0
                    for item in items
                ) / count,
                4,
            ),
        }

    return metrics


def evaluate_baseline(records, questions):
    retriever = Retriever(records)
    results = []

    for question in questions:
        ranked = retriever.search(
            question["question"],
            limit=len(records),
        )

        target_rank = None

        for rank, item in enumerate(ranked, start=1):
            if is_correct(item.record, question):
                target_rank = rank
                break

        top_results = [
            {
                "rank": rank,
                "protocol_id": item.record["protocol_id"],
                "step_id": item.record["step_id"],
                "step": item.record["step"],
                "score": round(float(item.score), 6),
            }
            for rank, item in enumerate(ranked[:TOP_K], start=1)
        ]

        results.append({
            "id": question["id"],
            "language": question["language"],
            "question": question["question"],
            "expected_protocol_id": question["expected_protocol_id"],
            "expected_step_id": question["expected_step_id"],
            "target_rank": target_rank,
            "top_results": top_results,
        })

    return results


def evaluate_e5(records, questions):
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    passages = [
        "passage: " + str(record["text"])
        for record in records
    ]
    queries = [
        "query: " + question["question"]
        for question in questions
    ]

    passage_vectors = model.encode(
        passages,
        batch_size=16,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    query_vectors = model.encode(
        queries,
        batch_size=16,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # Normalized vectors make the dot product equivalent to cosine similarity.
    similarity_matrix = np.matmul(query_vectors, passage_vectors.T)

    results = []

    for index, question in enumerate(questions):
        scores = similarity_matrix[index]
        ranked_indices = np.argsort(-scores)

        target_rank = None

        for rank, record_index in enumerate(ranked_indices, start=1):
            if is_correct(records[int(record_index)], question):
                target_rank = rank
                break

        top_results = []

        for rank, record_index in enumerate(ranked_indices[:TOP_K], start=1):
            record_index = int(record_index)
            record = records[record_index]

            top_results.append({
                "rank": rank,
                "protocol_id": record["protocol_id"],
                "step_id": record["step_id"],
                "step": record["step"],
                "score": round(float(scores[record_index]), 6),
            })

        results.append({
            "id": question["id"],
            "language": question["language"],
            "question": question["question"],
            "expected_protocol_id": question["expected_protocol_id"],
            "expected_step_id": question["expected_step_id"],
            "target_rank": target_rank,
            "top_results": top_results,
        })

    return results


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    records = load_active_protocols()
    questions = load_questions()

    if len(records) != 58:
        raise ValueError(
            f"Expected 58 protocol records, but found {len(records)}."
        )

    if len(questions) != 30:
        raise ValueError(
            f"Expected 30 evaluation questions, but found {len(questions)}."
        )

    print(f"Protocol records: {len(records)}")
    print(f"Evaluation questions: {len(questions)}")
    print("")

    print("Running existing hashed retrieval baseline...")
    baseline_results = evaluate_baseline(records, questions)
    baseline_metrics = calculate_metrics(baseline_results)

    print("Running multilingual E5 on CPU...")
    e5_results = evaluate_e5(records, questions)
    e5_metrics = calculate_metrics(e5_results)

    report = {
        "dataset": {
            "question_count": len(questions),
            "record_count": len(records),
            "languages": {
                "en": 10,
                "hi": 10,
                "hinglish": 10,
            },
        },
        "models": {
            "hashed_baseline": {
                "metrics": baseline_metrics,
                "results": baseline_results,
            },
            "multilingual_e5_small": {
                "model": MODEL_NAME,
                "device": "cpu",
                "metrics": e5_metrics,
                "results": e5_results,
            },
        },
    }

    json_path = RESULTS_DIR / "multilingual_retrieval_report.json"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    csv_path = RESULTS_DIR / "multilingual_retrieval_summary.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id",
                "language",
                "model",
                "expected_step_id",
                "target_rank",
                "top1_step_id",
                "top1_step",
                "top1_score",
                "top3_step_ids",
            ],
        )
        writer.writeheader()

        for model_name, model_results in [
            ("hashed_baseline", baseline_results),
            ("multilingual_e5_small", e5_results),
        ]:
            for result in model_results:
                top = result["top_results"]
                first = top[0] if top else {}

                writer.writerow({
                    "id": result["id"],
                    "language": result["language"],
                    "model": model_name,
                    "expected_step_id": result["expected_step_id"],
                    "target_rank": result["target_rank"],
                    "top1_step_id": first.get("step_id"),
                    "top1_step": first.get("step"),
                    "top1_score": first.get("score"),
                    "top3_step_ids": ",".join(
                        str(item["step_id"]) for item in top
                    ),
                })

    print("\n========== RETRIEVAL METRICS ==========")

    for model_name, metrics in [
        ("HASHED BASELINE", baseline_metrics),
        ("MULTILINGUAL E5", e5_metrics),
    ]:
        print(f"\n{model_name}")
        print(
            f'{"Language":<12}'
            f'{"Questions":<12}'
            f'{"Recall@1":<12}'
            f'{"Recall@3":<12}'
            f'{"MRR":<12}'
        )

        for language in ["en", "hi", "hinglish", "overall"]:
            item = metrics[language]
            print(
                f'{language:<12}'
                f'{item["questions"]:<12}'
                f'{item["recall_at_1"]:<12}'
                f'{item["recall_at_3"]:<12}'
                f'{item["mean_reciprocal_rank"]:<12}'
            )

    print("\n========== TOP-3 MISSES ==========")

    for model_name, model_results in [
        ("HASHED BASELINE", baseline_results),
        ("MULTILINGUAL E5", e5_results),
    ]:
        misses = [
            item for item in model_results
            if item["target_rank"] is None or item["target_rank"] > 3
        ]

        print(f"\n{model_name}: {len(misses)} questions missed at Recall@3")

        for item in misses:
            print(
                f'{item["id"]} | expected step '
                f'{item["expected_step_id"]} | '
                f'target rank: {item["target_rank"]}'
            )
            for candidate in item["top_results"]:
                print(
                    f'  {candidate["rank"]}. '
                    f'{candidate["step_id"]}: {candidate["step"]} '
                    f'(score={candidate["score"]})'
                )

    print("\nReports saved:")
    print(json_path)
    print(csv_path)
    print("\nRETRIEVAL EVALUATION COMPLETED")


if __name__ == "__main__":
    main()
