
"""Compare global E5 with procedure-aware E5 retrieval."""

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
DATASET_PATH = BASE_DIR / "multilingual_challenge_questions.json"
RESULTS_DIR = BASE_DIR / "results"

MODEL_NAME = "intfloat/multilingual-e5-small"
TOP_K = 3


def load_questions():
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        questions = json.load(file)

    if len(questions) != 60:
        raise ValueError(f"Expected 60 questions, found {len(questions)}")

    return questions


def is_correct(record, question):
    return (
        record["protocol_id"] == question["expected_protocol_id"]
        and record["step_id"] == question["expected_step_id"]
    )


def calculate_metrics(results):
    output = {}

    for language in sorted({x["language"] for x in results}):
        items = [x for x in results if x["language"] == language]

        output[language] = {
            "count": len(items),
            "recall_at_1": sum(
                x["target_rank"] == 1 for x in items
            ) / len(items),
            "recall_at_3": sum(
                x["target_rank"] is not None
                and x["target_rank"] <= TOP_K
                for x in items
            ) / len(items),
            "mrr": sum(
                1 / x["target_rank"]
                if x["target_rank"] is not None else 0
                for x in items
            ) / len(items),
        }

    if results:
        output["overall"] = {
            "count": len(results),
            "recall_at_1": sum(
                x["target_rank"] == 1 for x in results
            ) / len(results),
            "recall_at_3": sum(
                x["target_rank"] is not None
                and x["target_rank"] <= TOP_K
                for x in results
            ) / len(results),
            "mrr": sum(
                1 / x["target_rank"]
                if x["target_rank"] is not None else 0
                for x in results
            ) / len(results),
        }

    return output


def rank_records(scores, records, question):
    indices = np.argsort(scores)[::-1]

    target_rank = None
    candidates = []

    for rank, index in enumerate(indices, start=1):
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

    return {
        "id": question["id"],
        "language": question["language"],
        "question": question["question"],
        "action": question["expected_action"],
        "expected_protocol_id": question["expected_protocol_id"],
        "expected_step_id": question["expected_step_id"],
        "target_rank": target_rank,
        "top_results": candidates[:TOP_K],
    }


def main():
    questions = load_questions()
    records = load_active_protocols()

    if len(records) != 58:
        raise ValueError(f"Expected 58 records, found {len(records)}")

    protocols = {}

    for record in records:
        protocols[record["protocol_id"]] = {
            "name": record["protocol"],
            "description": record["protocol_description"],
        }

    if len(protocols) != 5:
        raise ValueError(f"Expected 5 procedures, found {len(protocols)}")

    print("Questions:", len(questions))
    print("Protocol records:", len(records))
    print("Procedure profiles:", len(protocols))

    print("\nLoading E5...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    # Stage 1: independently classify the procedure.
    profile_ids = sorted(protocols)

    profile_texts = [
        "passage: Procedure: "
        + protocols[pid]["name"]
        + "\nDescription: "
        + protocols[pid]["description"]
        for pid in profile_ids
    ]

    query_texts = [
        "query: " + question["question"]
        for question in questions
    ]

    profile_vectors = model.encode(
        profile_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    query_vectors = model.encode(
        query_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    procedure_scores = np.matmul(
        query_vectors,
        profile_vectors.T,
    )

    # Stage 2: global retrieval and procedure-filtered retrieval.
    global_passages = [
        "passage: " + str(record["text"])
        for record in records
    ]

    passage_vectors = model.encode(
        global_passages,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    global_similarities = np.matmul(
        query_vectors,
        passage_vectors.T,
    )

    global_results = []
    aware_results = []
    procedure_results = []

    for index, question in enumerate(questions):
        scores = procedure_scores[index]
        order = np.argsort(scores)[::-1]

        predicted_protocol_id = profile_ids[int(order[0])]

        procedure_results.append({
            "id": question["id"],
            "language": question["language"],
            "action": question["expected_action"],
            "predicted_protocol_id": predicted_protocol_id,
            "predicted_procedure": protocols[predicted_protocol_id]["name"],
            "top_procedures": [
                {
                    "protocol_id": profile_ids[int(i)],
                    "name": protocols[profile_ids[int(i)]]["name"],
                    "score": float(scores[i]),
                }
                for i in order
            ],
            "expected_protocol_id": (
                question["expected_protocol_id"]
                if question["expected_action"] == "retrieve_step"
                else None
            ),
            "correct": (
                predicted_protocol_id == question["expected_protocol_id"]
                if question["expected_action"] == "retrieve_step"
                else None
            ),
        })

        # Global E5: all 58 records.
        global_results.append(
            rank_records(
                global_similarities[index],
                records,
                question,
            )
        )

        # Procedure-aware E5: only the independently predicted procedure.
        filtered_pairs = [
            (i, record)
            for i, record in enumerate(records)
            if record["protocol_id"] == predicted_protocol_id
        ]

        filtered_indices = [i for i, _ in filtered_pairs]
        filtered_records = [record for _, record in filtered_pairs]
        filtered_scores = global_similarities[index][filtered_indices]

        aware_results.append(
            rank_records(
                filtered_scores,
                filtered_records,
                question,
            )
        )

    retrieval_global = [
        x for x in global_results if x["action"] == "retrieve_step"
    ]
    retrieval_aware = [
        x for x in aware_results if x["action"] == "retrieve_step"
    ]

    procedure_retrieval = [
        x for x in procedure_results if x["action"] == "retrieve_step"
    ]

    procedure_accuracy = {
        "count": len(procedure_retrieval),
        "overall": sum(x["correct"] for x in procedure_retrieval)
        / len(procedure_retrieval),
    }

    procedure_accuracy["by_language"] = {}

    for language in sorted({x["language"] for x in procedure_retrieval}):
        items = [
            x for x in procedure_retrieval
            if x["language"] == language
        ]
        procedure_accuracy["by_language"][language] = {
            "count": len(items),
            "accuracy": sum(x["correct"] for x in items) / len(items),
        }

    print("\nPROCEDURE CLASSIFICATION")
    print("Overall accuracy:", round(procedure_accuracy["overall"], 4))

    for language, values in procedure_accuracy["by_language"].items():
        print(
            f"{language}: {values['accuracy']:.4f} "
            f"({values['count']} questions)"
        )

    for name, results in (
        ("GLOBAL E5", retrieval_global),
        ("PROCEDURE-AWARE E5", retrieval_aware),
    ):
        print(f"\n{name}")

        for language, values in calculate_metrics(results).items():
            print(
                f"{language:10} | N={values['count']:2} | "
                f"R@1={values['recall_at_1']:.4f} | "
                f"R@3={values['recall_at_3']:.4f} | "
                f"MRR={values['mrr']:.4f}"
            )

    misses = [
        x for x in retrieval_aware
        if x["target_rank"] is None or x["target_rank"] > TOP_K
    ]

    print("\nPROCEDURE-AWARE TOP-3 MISSES:", len(misses))
    for item in misses:
        print(
            item["id"],
            "| expected step:", item["expected_step_id"],
            "| predicted procedure:",
            next(
                x["predicted_procedure"]
                for x in procedure_results
                if x["id"] == item["id"]
            ),
        )

    report = {
        "model": MODEL_NAME,
        "dataset": DATASET_PATH.name,
        "protocol_record_count": len(records),
        "procedure_count": len(protocols),
        "procedure_classification": {
            "metrics": procedure_accuracy,
            "results": procedure_results,
        },
        "global_e5": {
            "metrics": calculate_metrics(retrieval_global),
            "results": retrieval_global,
        },
        "procedure_aware_e5": {
            "metrics": calculate_metrics(retrieval_aware),
            "results": retrieval_aware,
        },
        "note": (
            "Experimental technical evaluation only. Procedure predictions "
            "are inferred from questions. Expected protocol IDs are used "
            "only for evaluation, never for prediction. Clarification "
            "questions are excluded from retrieval metrics. No clinical "
            "approval or validation is established."
        ),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    report_path = RESULTS_DIR / "procedure_aware_e5_report.json"
    csv_path = RESULTS_DIR / "procedure_aware_e5_summary.csv"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    csv_rows = []

    for result in procedure_results:
        global_item = next(
            x for x in global_results if x["id"] == result["id"]
        )
        aware_item = next(
            x for x in aware_results if x["id"] == result["id"]
        )

        csv_rows.append({
            "id": result["id"],
            "language": result["language"],
            "action": result["action"],
            "expected_protocol_id": result["expected_protocol_id"],
            "predicted_protocol_id": result["predicted_protocol_id"],
            "procedure_correct": result["correct"],
            "expected_step_id": global_item["expected_step_id"],
            "global_target_rank": global_item["target_rank"],
            "procedure_aware_target_rank": aware_item["target_rank"],
            "procedure_aware_top1_step": (
                aware_item["top_results"][0]["step_id"]
                if aware_item["top_results"] else ""
            ),
        })

    with csv_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)

    print("\nEXPERIMENT COMPLETE")
    print("JSON:", report_path)
    print("CSV:", csv_path)
    print("Original benchmark files were not modified.")


if __name__ == "__main__":
    main()
