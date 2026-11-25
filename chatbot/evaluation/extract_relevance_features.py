"""Generate E5 features for experimental ANN relevance training."""

from __future__ import annotations

import os
import json
import time
import hashlib

from pathlib import Path
from importlib.metadata import version

import numpy as np

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

import django
django.setup()

from chatbot.ann.e5_retrieval import _get_model

from chatbot.ann.relevance_features import (
    build_pair_features,
    FEATURE_VERSION,
    FEATURE_DIM,
    EMBEDDING_DIM,
)

from chatbot.evaluation.load_protocols import (
    load_active_protocols,
)


ROOT = Path(__file__).resolve().parent.parent

SOURCE = (
    ROOT
    / "datasets"
    / "relevance_training_experimental_v1.jsonl"
)

OUTPUT = (
    ROOT
    / "datasets"
    / "relevance_features_experimental_v1.npz"
)

METADATA = (
    ROOT
    / "datasets"
    / "relevance_features_experimental_v1.json"
)


def main():

    if OUTPUT.exists() or METADATA.exists():
        raise SystemExit(
            "Feature artifacts already exist. "
            "No changes made."
        )

    started = time.perf_counter()

    source_bytes = SOURCE.read_bytes()

    rows = [
        json.loads(line)
        for line in source_bytes.decode(
            "utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != 153:
        raise ValueError(
            "Unexpected training dataset size"
        )

    if not all(
        row["experimental_only"] is True
        and row["clinical_approval"] is False
        for row in rows
    ):
        raise ValueError(
            "Unexpected training approval metadata"
        )

    records = {
        (record["protocol_id"], record["step_id"]):
        record
        for record in load_active_protocols()
    }

    query_texts = []
    passage_texts = []

    for row in rows:

        key = (
            row["protocol_id"],
            row["step_id"],
        )

        record = records.get(key)

        if record is None:
            raise ValueError(
                f"Missing stored evidence: {key}"
            )

        current_hash = hashlib.sha256(
            record["instruction"].strip().encode(
                "utf-8"
            )
        ).hexdigest()

        if (
            current_hash
            != row["instruction_sha256"]
        ):
            raise ValueError(
                f"Stored instruction changed: {key}"
            )

        query_texts.append(
            "query: " + row["question"]
        )

        passage_texts.append(
            "passage: " + record["text"]
        )

    unique_queries = list(
        dict.fromkeys(query_texts)
    )

    unique_passages = list(
        dict.fromkeys(passage_texts)
    )

    print(
        "Training pairs:", len(rows),
        flush=True,
    )

    print(
        "Unique queries:", len(unique_queries),
        flush=True,
    )

    print(
        "Unique passages:", len(unique_passages),
        flush=True,
    )

    print(
        "Loading cached multilingual E5 model...",
        flush=True,
    )

    model = _get_model()

    print(
        "Encoding unique questions...",
        flush=True,
    )

    query_vectors = model.encode(
        unique_queries,
        batch_size=16,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    print(
        "Encoding unique passages...",
        flush=True,
    )

    passage_vectors = model.encode(
        unique_passages,
        batch_size=16,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    query_vectors = np.asarray(
        query_vectors,
        dtype=np.float32,
    )

    passage_vectors = np.asarray(
        passage_vectors,
        dtype=np.float32,
    )

    assert query_vectors.shape == (
        len(unique_queries),
        EMBEDDING_DIM,
    )

    assert passage_vectors.shape == (
        len(unique_passages),
        EMBEDDING_DIM,
    )

    query_map = dict(
        zip(unique_queries, query_vectors)
    )

    passage_map = dict(
        zip(unique_passages, passage_vectors)
    )

    X = np.stack([
        build_pair_features(
            query_map[query],
            passage_map[passage],
        )
        for query, passage in zip(
            query_texts,
            passage_texts,
        )
    ]).astype(np.float32)

    y = np.asarray([
        row["target"]
        for row in rows
    ], dtype=np.int64)

    groups = np.asarray([
        row["question_family_id"]
        for row in rows
    ])

    pair_ids = np.asarray([
        row["pair_id"]
        for row in rows
    ])

    languages = np.asarray([
        row["language"]
        for row in rows
    ])

    question_ids = np.asarray([
        row["question_id"]
        for row in rows
    ])

    assert X.shape == (153, FEATURE_DIM)
    assert y.shape == (153,)
    assert np.isfinite(X).all()

    assert int(y.sum()) == 55
    assert len(set(groups)) == 10
    assert len(set(pair_ids)) == 153
    assert len(set(question_ids)) == 60

    np.savez_compressed(
        OUTPUT,
        X=X,
        y=y,
        groups=groups,
        pair_ids=pair_ids,
        languages=languages,
        question_ids=question_ids,
    )

    elapsed = time.perf_counter() - started

    metadata = {
        "feature_version": FEATURE_VERSION,
        "encoder": "intfloat/multilingual-e5-small",
        "embedding_dimensions": EMBEDDING_DIM,
        "feature_dimensions": FEATURE_DIM,
        "dataset_sha256": hashlib.sha256(
            source_bytes
        ).hexdigest(),
        "feature_file_sha256": hashlib.sha256(
            OUTPUT.read_bytes()
        ).hexdigest(),
        "training_pairs": len(rows),
        "unique_queries": len(unique_queries),
        "unique_passages": len(unique_passages),
        "question_families": len(set(groups)),
        "positive_examples": int(y.sum()),
        "negative_examples": int(len(y) - y.sum()),
        "packages": {
            name: version(name)
            for name in (
                "torch",
                "sentence-transformers",
                "transformers",
                "numpy",
                "scikit-learn",
            )
        },
        "experimental_only": True,
        "clinical_approval": False,
        "elapsed_seconds": round(elapsed, 3),
    }

    with METADATA.open(
        "x",
        encoding="utf-8",
    ) as handle:
        json.dump(
            metadata,
            handle,
            indent=2,
        )

    with np.load(
        OUTPUT,
        allow_pickle=False,
    ) as saved:
        assert np.array_equal(saved["X"], X)
        assert np.array_equal(saved["y"], y)
        assert np.array_equal(
            saved["groups"],
            groups,
        )

    print("\n--- FEATURE EXTRACTION RESULTS ---")
    print("Feature matrix:", X.shape)
    print("Target vector:", y.shape)
    print("Data type:", X.dtype)
    print("Positive examples:", int(y.sum()))
    print("Negative examples:", len(y) - int(y.sum()))
    print("Question families:", len(set(groups)))
    print("Finite features: PASS")
    print("Artifact round-trip verification: PASS")
    print("Elapsed seconds:", round(elapsed, 3))
    print("Features saved:", OUTPUT)
    print("Metadata saved:", METADATA)
    print("NEURAL FEATURE EXTRACTION COMPLETED")


if __name__ == "__main__":
    main()
