"""Offline reviewed-experience retraining and checkpoint loading."""

import json
import hashlib
import tempfile
import uuid

from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np
import torch

from safetensors.torch import save_file, load

from chatbot.ann.relevance_model import RelevanceANN

from chatbot.ann.relevance_features import (
    build_pair_features,
    FEATURE_VERSION,
    FEATURE_DIM,
)

from chatbot.ann.learning_export import (
    export_approved_examples,
)

from chatbot.ann.e5_retrieval import _get_model

from chatbot.evaluation.load_protocols import (
    load_active_protocols,
)

from chatbot.evaluation.train_relevance_ranker import (
    train_ranker,
    rank_scores,
    VERSION,
    COSINE_SCALE,
    EPOCHS,
    SEED,
)


MIN_COMPETITIVE_QUESTIONS = 10
MIN_PROTOCOLS = 2


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _dataset_hash(rows):

    return _sha256(
        json.dumps(
            rows,
            sort_keys=True,
            ensure_ascii=True,
        ).encode("utf-8")
    )


def load_experimental_ranker(directory):

    directory = Path(directory)

    manifest = json.loads(
        (directory / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    expected = {
        "model_version": VERSION,
        "feature_version": FEATURE_VERSION,
        "encoder": "intfloat/multilingual-e5-small",
        "input_dimensions": FEATURE_DIM,
        "hidden_dimensions": 16,
        "dropout": 0.3,
        "cosine_scale": COSINE_SCALE,
    }

    for key, value in expected.items():

        if manifest.get(key) != value:
            raise ValueError(
                f"Incompatible checkpoint field: {key}"
            )

    if not (
        manifest.get("experimental_only") is True
        and manifest.get("clinical_approval") is False
        and manifest.get("production_enabled") is False
    ):
        raise ValueError(
            "Expected an experimental-only checkpoint."
        )

    weights = (
        directory / "weights.safetensors"
    ).read_bytes()

    if _sha256(weights) != manifest.get("weights_sha256"):
        raise ValueError("Checkpoint integrity failure.")

    state = load(weights)

    if not all(
        torch.isfinite(value).all()
        for value in state.values()
    ):
        raise ValueError("Non-finite checkpoint weights.")

    model = RelevanceANN()

    model.load_state_dict(state, strict=True)
    model.eval()

    return model, manifest


def retrain_from_reviewed_experiences(
    *,
    user,
    output_root,
):

    rows = export_approved_examples(user=user)

    if not rows:
        raise ValueError(
            "No approved learning examples available."
        )

    source_hash = _dataset_hash(rows)

    grouped = defaultdict(list)
    escalation = defaultdict(set)

    for row in rows:

        if not (
            row["review_status"] == "approved"
            and row["experimental_only"] is True
            and row["clinical_release_approved"] is False
        ):
            raise ValueError(
                "Unexpected review eligibility."
            )

        normalized = " ".join(
            row["question"].casefold().split()
        )

        question_key = (
            row["protocol_id"],
            normalized,
        )

        grouped[question_key].append(row)

        escalation[question_key].add(
            row["requires_escalation"]
        )

    if any(
        len(flags) != 1
        for flags in escalation.values()
    ):
        raise ValueError(
            "Inconsistent question escalation labels."
        )

    competitive = {
        key: examples
        for key, examples in grouped.items()
        if {row["target"] for row in examples} == {0, 1}
    }

    if len(competitive) < MIN_COMPETITIVE_QUESTIONS:
        raise ValueError(
            "Insufficient competitive reviewed questions."
        )

    protocols = {
        key[0] for key in competitive
    }

    if len(protocols) < MIN_PROTOCOLS:
        raise ValueError(
            "Insufficient reviewed protocol diversity."
        )

    records = {
        (row["protocol_id"], row["step_id"]): row
        for row in load_active_protocols()
    }

    queries = []
    passages = []
    targets = []
    question_ids = []

    for key, examples in sorted(competitive.items()):

        question_id = _sha256(
            json.dumps(key).encode("utf-8")
        )

        for row in examples:

            record = records.get((
                row["protocol_id"],
                row["step_id"],
            ))

            if record is None:
                raise ValueError(
                    "Reviewed instruction unavailable."
                )

            current = record["instruction"].strip()

            if (
                _sha256(current.encode("utf-8"))
                != row["instruction_sha256"]
                or current != row["instruction"]
            ):
                raise ValueError(
                    "Reviewed instruction changed."
                )

            queries.append(
                "query: " + row["question"]
            )

            passages.append(
                "passage: " + record["text"]
            )

            targets.append(row["target"])
            question_ids.append(question_id)

    model = _get_model()

    unique_queries = list(dict.fromkeys(queries))
    unique_passages = list(dict.fromkeys(passages))

    def encode(texts):

        vectors = model.encode(
            texts,
            batch_size=16,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        if len(vectors) != len(texts):
            raise ValueError(
                "Unexpected embedding count."
            )

        return dict(zip(texts, vectors))

    query_vectors = encode(unique_queries)
    passage_vectors = encode(unique_passages)

    X = np.stack([
        build_pair_features(
            query_vectors[query],
            passage_vectors[passage],
        )
        for query, passage in zip(
            queries,
            passages,
        )
    ]).astype(np.float32)

    y = np.asarray(targets, dtype=np.int64)
    question_ids = np.asarray(question_ids)

    trained, training = train_ranker(
        X,
        y,
        question_ids,
        SEED,
    )

    # Recheck eligibility after training.
    current_rows = export_approved_examples(user=user)

    if _dataset_hash(current_rows) != source_hash:
        raise ValueError(
            "Reviewed dataset changed during training."
        )

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    output = output_root / (
        f"{VERSION}_{timestamp}_{uuid.uuid4().hex[:8]}"
    )

    with tempfile.TemporaryDirectory(
        dir=output_root
    ) as temporary:

        staging = Path(temporary) / "checkpoint"
        staging.mkdir()

        weights_path = staging / "weights.safetensors"

        save_file(
            {
                key: value.detach().cpu().contiguous()
                for key, value
                in trained.state_dict().items()
            },
            str(weights_path),
        )

        manifest = {
            "model_version": VERSION,
            "feature_version": FEATURE_VERSION,
            "encoder": "intfloat/multilingual-e5-small",
            "encoder_revision_verified": False,
            "input_dimensions": FEATURE_DIM,
            "hidden_dimensions": 16,
            "dropout": 0.3,
            "cosine_scale": COSINE_SCALE,
            "epochs": EPOCHS,
            "seed": SEED,
            "dataset_sha256": source_hash,
            "weights_sha256": _sha256(
                weights_path.read_bytes()
            ),
            "training_source": "reviewed_experiences_only",
            "exported_examples": len(rows),
            "training_pairs": len(y),
            "competitive_questions": len(competitive),
            "protocol_count": len(protocols),
            "training": training,
            "independent_validation_completed": False,
            "experimental_only": True,
            "clinical_approval": False,
            "production_enabled": False,
        }

        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        restored, _ = load_experimental_ranker(
            staging
        )

        with torch.inference_mode():

            features = torch.from_numpy(X)

            if not torch.allclose(
                rank_scores(trained, features),
                rank_scores(restored, features),
                atol=1e-7,
            ):
                raise RuntimeError(
                    "Checkpoint verification failed."
                )

        if output.exists():
            raise FileExistsError(output)

        staging.rename(output)

    return output
